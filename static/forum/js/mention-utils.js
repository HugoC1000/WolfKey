/**
 * Unified Mention Rendering Utilities
 * Shared logic for rendering mentions across all components:
 * - Post details
 * - Solutions
 * - Comments
 * - Any other content with mentions
 * 
 * Supports:
 * - @username mentions (users)
 * - #coursename mentions (courses)
 * - @everyone mentions (admin-only)
 */

export class MentionUtils {
  // Regex patterns for different mention types
  // @username or @everyone
  static userMentionRegex = /@([\w.-]+)/g;
  // #course_id-name or #coursename (backwards compatibility)
  static courseMentionRegex = /#(course_\d+-[^#\s]+|[\w\s.-]+?)(?=\s|$|[^a-zA-Z0-9\s._-])/g;

  /**
   * Render mentions in plain text by converting mentions to HTML links
   * Supports: @username, #coursename, @everyone
   * Safe for use in contexts where you need HTML output
   * 
   * @param {string} text - The text to render mentions in
   * @returns {string} HTML with mentions converted to links
   */
  static renderText(text) {
    if (!text || typeof text !== 'string') {
      return text;
    }

    // First render user mentions (@username, @everyone)
    text = text.replace(
      this.userMentionRegex,
      (match, username) => {
        const escaped = this.escape(username);
        if (username.toLowerCase() === 'everyone') {
          return `<a href="#" class="mention mention-everyone" title="Mention: everyone" data-mention-type="everyone">@${escaped}</a>`;
        }
        return `<a href="/profile/${escaped}/" class="mention mention-user" title="View ${escaped}'s profile">@${escaped}</a>`;
      }
    );

    // Then render course mentions (#coursename or #course_id-name)
    text = text.replace(
      this.courseMentionRegex,
      (match, courseIdentifier) => {
        let courseId = null;
        let courseName = courseIdentifier;
        
        // Check if it's the new format: course_id-name
        const courseIdMatch = courseIdentifier.match(/^course_(\d+)-(.+)$/);
        if (courseIdMatch) {
          courseId = courseIdMatch[1];
          courseName = courseIdMatch[2];
        }
        
        const escaped = this.escape(courseName.trim());
        return `<a href="#" class="mention mention-course" title="Course: ${escaped}" data-mention-type="course" data-course-id="${courseId}" data-course-name="${escaped}">#${escaped}</a>`;
      }
    );

    return text;
  }

  /**
   * Render mentions in HTML element (modifies element in place)
   * Walks through all text nodes and converts mentions to links
   * Supports: @username, #coursename, @everyone
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
      if (parentElement && (parentElement.classList.contains('mention') || parentElement.classList.contains('mention-user') || parentElement.classList.contains('mention-course'))) {
        continue;
      }

      // Check if text contains mentions
      const text = node.textContent || '';
      if (text.includes('@') || text.includes('#')) {
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
   * Handles user mentions (@username, @everyone) and course mentions (#coursename)
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

    // Process both user and course mentions
    let lastIndex = 0;
    const mentions = [];

    // Find all user mentions
    this.resetRegex();
    let match;
    while ((match = this.userMentionRegex.exec(text)) !== null) {
      mentions.push({
        type: 'user',
        start: match.index,
        end: match.index + match[0].length,
        fullMatch: match[0],
        username: match[1]
      });
    }

    // Find all course mentions
    this.courseMentionRegex.lastIndex = 0;
    while ((match = this.courseMentionRegex.exec(text)) !== null) {
      const courseIdentifier = match[1].trim();
      let courseId = null;
      let courseName = courseIdentifier;
      
      // Check if it's the new format: course_id-name
      const courseIdMatch = courseIdentifier.match(/^course_(\d+)-(.+)$/);
      if (courseIdMatch) {
        courseId = courseIdMatch[1];
        courseName = courseIdMatch[2];
      }
      
      mentions.push({
        type: 'course',
        start: match.index,
        end: match.index + match[0].length,
        fullMatch: match[0],
        courseid: courseId,
        coursename: courseName
      });
    }

    // Sort mentions by start position
    mentions.sort((a, b) => a.start - b.start);

    // Remove overlapping mentions (keep first)
    const finalMentions = [];
    for (let mention of mentions) {
      const isOverlapping = finalMentions.some(m => 
        (mention.start < m.end && mention.end > m.start)
      );
      if (!isOverlapping) {
        finalMentions.push(mention);
      }
    }

    // Build fragment with mentions
    lastIndex = 0;
    finalMentions.forEach(mention => {
      // Add text before mention
      if (mention.start > lastIndex) {
        fragment.appendChild(document.createTextNode(text.slice(lastIndex, mention.start)));
      }

      // Create mention link
      const link = document.createElement('a');
      link.className = `mention mention-${mention.type}`;
      link.setAttribute('data-mention-type', mention.type);

      if (mention.type === 'user') {
        const username = mention.username;
        if (username.toLowerCase() === 'everyone') {
          link.href = '#';
          link.title = 'Mention: everyone';
        } else {
          link.href = `/profile/${encodeURIComponent(username)}/`;
          link.title = `View ${username}'s profile`;
        }
        link.textContent = mention.fullMatch;
      } else if (mention.type === 'course') {
        link.href = '#';
        link.title = `Course: ${mention.coursename}`;
        link.setAttribute('data-course-name', mention.coursename);
        if (mention.courseid) {
          link.setAttribute('data-course-id', mention.courseid);
        }
        link.textContent = mention.fullMatch;
      }

      fragment.appendChild(link);
      lastIndex = mention.end;
    });

    // Add remaining text after last mention
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
    this.userMentionRegex.lastIndex = 0;
    this.courseMentionRegex.lastIndex = 0;
  }
}

export default MentionUtils;
