/**
 * Unified Mention Rendering Utilities
 * Shared logic for rendering @username mentions across all components:
 * - Post details
 * - Solutions
 * - Comments
 * - Any other content with mentions
 */

export class MentionUtils {
  // Regex pattern for @username mentions
  // Matches: @username, @user.name, @user-name, @user_name
  static mentionRegex = /@([\w.-]+)/g;

  /**
   * Render mentions in plain text by converting @username to HTML links
   * Safe for use in contexts where you need HTML output
   * 
   * @param {string} text - The text to render mentions in
   * @returns {string} HTML with @username converted to links
   */
  static renderText(text) {
    if (!text || typeof text !== 'string') {
      return text;
    }

    return text.replace(
      this.mentionRegex,
      (match, username) => {
        const escaped = this.escape(username);
        return `<a href="/profile/${escaped}/" class="mention" title="View ${escaped}'s profile">@${escaped}</a>`;
      }
    );
  }

  /**
   * Render mentions in HTML element (modifies element in place)
   * Walks through all text nodes and converts mentions to links
   * Used for Editor.js read-only rendering
   * 
   * @param {HTMLElement} element - The element to render mentions in
   */
  static renderElement(element) {
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

    // Replace text nodes using DOM APIs to avoid unsafe HTML injection
    nodesToReplace.forEach(node => {
      const fragment = this.createMentionFragment(node.textContent || '');
      if (node.parentElement) {
        node.parentElement.replaceChild(fragment, node);
      }
    });

    this.resetRegex();
  }

  /**
   * Build a safe document fragment with mention links and plain text nodes
   * Helper method used by renderElement()
   * 
   * @param {string} text - The text to process
   * @returns {DocumentFragment} Fragment with mention links and text nodes
   */
  static createMentionFragment(text) {
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

      // Add text before the mention
      if (start > lastIndex) {
        fragment.appendChild(document.createTextNode(text.slice(lastIndex, start)));
      }

      // Create mention link
      const link = document.createElement('a');
      link.href = `/profile/${encodeURIComponent(username)}/`;
      link.className = 'mention';
      link.title = `View ${username}'s profile`;
      link.textContent = fullMatch;
      fragment.appendChild(link);

      lastIndex = start + fullMatch.length;
    }

    // Add remaining text after the last mention
    if (lastIndex < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
    }

    return fragment;
  }

  /**
   * Escape HTML special characters for safe use in HTML attributes
   * 
   * @param {string} text - Text to escape
   * @returns {string} Escaped text
   */
  static escape(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Reset regex state (important because of global flag)
   * Must be called before starting new searches
   */
  static resetRegex() {
    this.mentionRegex.lastIndex = 0;
  }
}

export default MentionUtils;
