from django import template
from django.utils.safestring import mark_safe

from forum.services.content_format import get_markdown, render_markdown

register = template.Library()


@register.filter
def render_forum_markdown(content_obj):
    return mark_safe(render_markdown(get_markdown(content_obj)))
