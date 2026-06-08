/**
 * MentionRenderer
 * Converts @username text to clickable links
 */
class MentionRenderer {
  constructor() {
    // Regex to find @username patterns
    // Username can contain letters, numbers, underscores, dots, hyphens
    this.mentionRegex = /@([\w.-]+)/g;
  }

  /**
   * Render mentions in plain text by converting @username to links
   * @param {string} text - The text to render mentions in
   * @returns {string} HTML with @username converted to links
   */
  renderText(text) {
    if (!text || typeof text !== 'string') {
      return text;
    }

    return text.replace(
      this.mentionRegex,
      (match, username) => {
        return `<a href="/profile/${this.escape(username)}" class="mention" title="View ${this.escape(username)}'s profile">@${this.escape(username)}</a>`;
      }
    );
  }

  /**
   * Render mentions in HTML content (for EditorJS blocks)
   * Works with paragraph blocks that have text
   * @param {Object} block - EditorJS block object
   * @returns {string} HTML content with mentions rendered as links
   */
  renderBlock(block) {
    if (!block || !block.data) {
      return '';
    }

    let text = block.data.text || '';
    if (!text) {
      return '';
    }

    return this.renderText(text);
  }

  /**
   * Render mentions in a full EditorJS content object
   * Returns HTML for all blocks with mentions rendered
   * @param {Object} content - EditorJS content object
   * @returns {Array} Array of HTML strings for each block
   */
  renderContent(content) {
    if (!content || !content.blocks) {
      return [];
    }

    return content.blocks.map(block => {
      if (block.type === 'paragraph' || block.type === 'header') {
        return this.renderBlock(block);
      }
      return '';
    });
  }

  /**
   * Render mentions in HTML element (modifies element in place)
   * Finds all text nodes and converts mentions to links
   * @param {HTMLElement} element - The element to render mentions in
   */
  renderElement(element) {
    if (!element) return;

    // Walk through all text nodes
    const walker = document.createTreeWalker(
      element,
      NodeFilter.SHOW_TEXT,
      null,
      false
    );

    const nodesToReplace = [];
    let node;
    while (node = walker.nextNode()) {
      const parentElement = node.parentElement;

      // Skip if already inside a mention link
      if (parentElement && parentElement.classList.contains('mention')) {
        continue;
      }

      // Check if text contains mentions
      if (node.textContent && node.textContent.includes('@')) {
        nodesToReplace.push(node);
      }
    }

    // Replace text nodes using DOM APIs to avoid unsafe HTML injection.
    nodesToReplace.forEach(node => {
      const fragment = this.createMentionFragment(node.textContent || '');
      if (node.parentElement) {
        node.parentElement.replaceChild(fragment, node);
      }
    });

    this.resetRegex();
  }

  /**
   * Build a safe document fragment with mention links and plain text nodes.
   */
  createMentionFragment(text) {
    const fragment = document.createDocumentFragment();
    if (!text || typeof text !== 'string') {
      return fragment;
    }

    let lastIndex = 0;
    this.resetRegex();

    let match;
    while ((match = this.mentionRegex.exec(text)) !== null) {
      const [fullMatch, username] = match;
      const start = match.index;

      if (start > lastIndex) {
        fragment.appendChild(document.createTextNode(text.slice(lastIndex, start)));
      }

      const link = document.createElement('a');
      link.href = `/profile/${encodeURIComponent(username)}`;
      link.className = 'mention';
      link.title = `View ${username}'s profile`;
      link.textContent = fullMatch;
      fragment.appendChild(link);

      lastIndex = start + fullMatch.length;
    }

    if (lastIndex < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
    }

    return fragment;
  }

  /**
   * Escape HTML special characters
   */
  escape(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Reset regex state (important because of global flag)
   */
  resetRegex() {
    this.mentionRegex.lastIndex = 0;
  }
}

export default MentionRenderer;
