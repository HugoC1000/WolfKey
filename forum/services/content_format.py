"""The two stored representations of forum writing.

Editor.js remains the compatibility representation. Markdown is the source used by
new clients. Conversions happen on writes, never when serializing a response.
"""

import html
import json
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

import nh3
from markdown_it import MarkdownIt

logging.getLogger('markdown_it').setLevel(logging.WARNING)

_PARSER = MarkdownIt('commonmark', {'html': False, 'linkify': False}).enable(
    ['table', 'strikethrough']
)
_SAFE_TAGS = {
    'a', 'blockquote', 'br', 'code', 'del', 'em', 'h1', 'h2', 'h3', 'h4',
    'h5', 'h6', 'hr', 'img', 'li', 'ol', 'p', 'pre', 's', 'strong', 'table',
    'tbody', 'td', 'th', 'thead', 'tr', 'ul',
}
_INLINE_TAGS = {'a', 'br', 'code', 'del', 'em', 's', 'strong'}


def safe_url(url):
    if not isinstance(url, str):
        return False
    url = url.strip()
    if not url or any(ord(char) < 32 for char in url):
        return False
    parts = urlsplit(url)
    return parts.scheme.lower() in ('http', 'https', 'mailto') or (
        not parts.scheme and not url.startswith('//') and url.startswith('/')
    )


class _InlineHTMLToMarkdown(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in ('b', 'strong'):
            self.parts.append('**')
        elif tag in ('i', 'em'):
            self.parts.append('*')
        elif tag in ('s', 'del', 'strike'):
            self.parts.append('~~')
        elif tag == 'code':
            self.parts.append('`')
        elif tag == 'br':
            self.parts.append('  \n')
        elif tag == 'a':
            href = attributes.get('href', '')
            self.links.append(href if safe_url(href) else '')
            if self.links[-1]:
                self.parts.append('[')

    def handle_endtag(self, tag):
        if tag in ('b', 'strong'):
            self.parts.append('**')
        elif tag in ('i', 'em'):
            self.parts.append('*')
        elif tag in ('s', 'del', 'strike'):
            self.parts.append('~~')
        elif tag == 'code':
            self.parts.append('`')
        elif tag == 'a' and self.links:
            href = self.links.pop()
            if href:
                self.parts.append(f']({href})')

    def handle_data(self, data):
        self.parts.append(data)


def _inline_to_markdown(value):
    if not isinstance(value, str):
        return str(value or '')
    parser = _InlineHTMLToMarkdown()
    parser.feed(value)
    return ''.join(parser.parts).strip()


def _legacy_document(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return {'blocks': [{'type': 'paragraph', 'data': {'text': value}}]}
    if not isinstance(value, dict) or not isinstance(value.get('blocks'), list):
        return {'blocks': []}
    return value


def editorjs_to_markdown(value):
    """Preserve known block content; unknown blocks remain readable as plain text."""
    sections = []
    for block in _legacy_document(value)['blocks']:
        if not isinstance(block, dict):
            continue
        kind = block.get('type')
        data = block.get('data') or {}
        if not isinstance(data, dict):
            continue
        if kind in ('paragraph', 'header', 'heading', 'quote'):
            text = _inline_to_markdown(data.get('text', ''))
            if kind in ('header', 'heading'):
                level = max(1, min(6, int(data.get('level') or 2)))
                text = f'{"#" * level} {text}'
            elif kind == 'quote':
                text = '\n'.join(f'> {line}' for line in text.splitlines())
            sections.append(text)
        elif kind == 'list':
            lines = []
            for index, item in enumerate(data.get('items') or []):
                text = _inline_to_markdown(item.get('content', '') if isinstance(item, dict) else item)
                prefix = f'{index + 1}.' if data.get('style') == 'ordered' else '-'
                lines.append(f'{prefix} {text}')
            sections.append('\n'.join(lines))
        elif kind == 'code':
            code = str(data.get('code') or '').rstrip('\n')
            fence = '`' * max(3, max((len(match.group()) for match in re.finditer(r'`+', code)), default=0) + 1)
            sections.append(f'{fence}{data.get("language") or ""}\n{code}\n{fence}')
        elif kind == 'math':
            sections.append(f'$$\n{data.get("content") or ""}\n$$')
        elif kind == 'image':
            file_data = data.get('file') or {}
            url = file_data.get('url') if isinstance(file_data, dict) else file_data
            url = url or data.get('url')
            if safe_url(url):
                caption = _inline_to_markdown(data.get('caption') or '')
                sections.append(f'![{caption}]({url})')
        elif kind == 'delimiter':
            sections.append('---')
        else:
            text = _inline_to_markdown(data.get('text') or data.get('content') or '')
            if text:
                sections.append(text)
    return '\n\n'.join(section for section in sections if section).strip()


def _inline_html(token):
    rendered = _PARSER.renderer.render([token], _PARSER.options, {})
    return nh3.clean(
        rendered, tags=_INLINE_TAGS,
        attributes={'a': {'href', 'title'}},
        url_schemes={'http', 'https', 'mailto'},
    )


def markdown_to_editorjs(markdown):
    if not isinstance(markdown, str):
        raise ValueError('Markdown content must be a string.')
    blocks = []
    tokens = _PARSER.parse(markdown)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type in ('paragraph_open', 'heading_open') and index + 1 < len(tokens):
            inline = tokens[index + 1]
            if inline.type == 'inline':
                math = re.fullmatch(r'\$\$\s*\n?(.*?)\n?\s*\$\$', inline.content, re.DOTALL)
                if math:
                    blocks.append({'type': 'math', 'data': {'content': math.group(1).strip()}})
                    index += 3
                    continue
                children = inline.children or []
                images = [child for child in children if child.type == 'image']
                if len(images) == 1 and len(children) == 1:
                    image = images[0]
                    url = image.attrGet('src')
                    if safe_url(url):
                        blocks.append({'type': 'image', 'data': {
                            'file': {'url': url}, 'caption': image.content or '',
                        }})
                else:
                    data = {'text': _inline_html(inline)}
                    if token.type == 'heading_open':
                        data['level'] = int(token.tag[1:])
                    if data['text']:
                        blocks.append({'type': 'header' if token.type == 'heading_open' else 'paragraph', 'data': data})
                    for image in images:
                        url = image.attrGet('src')
                        if safe_url(url):
                            blocks.append({'type': 'image', 'data': {
                                'file': {'url': url}, 'caption': image.content or '',
                            }})
                index += 3
                continue
        if token.type in ('bullet_list_open', 'ordered_list_open'):
            ordered = token.type == 'ordered_list_open'
            items = []
            index += 1
            while index < len(tokens) and tokens[index].type not in ('bullet_list_close', 'ordered_list_close'):
                if tokens[index].type == 'inline':
                    items.append(_inline_html(tokens[index]))
                index += 1
            blocks.append({'type': 'list', 'data': {'style': 'ordered' if ordered else 'unordered', 'items': items}})
        elif token.type in ('fence', 'code_block'):
            blocks.append({'type': 'code', 'data': {'code': token.content.rstrip('\n'), 'language': token.info.strip()}})
        elif token.type == 'hr':
            blocks.append({'type': 'delimiter', 'data': {}})
        elif token.type == 'table_open':
            cells = []
            while index < len(tokens) and tokens[index].type != 'table_close':
                if tokens[index].type == 'inline':
                    cells.append(html.escape(tokens[index].content))
                elif tokens[index].type == 'tr_close':
                    cells.append('<br>')
                index += 1
            blocks.append({'type': 'paragraph', 'data': {'text': ' | '.join(cells)}})
        elif token.type == 'html_block':
            blocks.append({'type': 'paragraph', 'data': {'text': html.escape(token.content)}})
        index += 1
    return {'blocks': blocks}


def render_markdown(markdown):
    if not isinstance(markdown, str):
        return ''
    return nh3.clean(
        _PARSER.render(markdown), tags=_SAFE_TAGS,
        attributes={'a': {'href', 'title'}, 'img': {'src', 'alt', 'title'}},
        url_schemes={'http', 'https', 'mailto'},
    )


def markdown_plain_text(markdown):
    from django.utils.html import strip_tags
    rendered = re.sub(r'</(?:p|li|h[1-6]|pre|tr)>', '\n', render_markdown(markdown))
    return html.unescape(strip_tags(rendered)).strip()


def markdown_image_urls(markdown):
    urls = []
    for token in _PARSER.parse(markdown or ''):
        for child in token.children or []:
            if child.type == 'image' and safe_url(child.attrGet('src')):
                urls.append(child.attrGet('src'))
    return urls


def set_content_representations(obj, content, source_format='editorjs'):
    """Set both fields before save; the submitted format remains unchanged."""
    if source_format == 'markdown':
        if not isinstance(content, str):
            raise ValueError('Markdown content must be a string.')
        obj.content_markdown = content.strip()
        obj.content = markdown_to_editorjs(obj.content_markdown)
    elif source_format == 'editorjs':
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except ValueError:
                # Older web comment callers submitted plain text to the JSON
                # endpoint; keep accepting it as a single paragraph block.
                content = {'blocks': [{'type': 'paragraph', 'data': {'text': content}}]}
        if not isinstance(content, dict) or not isinstance(content.get('blocks'), list):
            raise ValueError('Editor.js content must have a blocks array.')
        obj.content = content
        obj.content_markdown = editorjs_to_markdown(content)
    else:
        raise ValueError('Unsupported content format.')


def get_markdown(obj):
    value = getattr(obj, 'content_markdown', None)
    return value if value is not None else editorjs_to_markdown(obj.content)
