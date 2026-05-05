/**
 * Mention Handler for Editor.js
 * Handles @mentions with autocomplete dropdown
 */

import MentionDropdown from './mention-dropdown.js';

export class MentionHandler {
  constructor(editor, options = {}) {
    this.editor = editor;
    this.editorElement = null;
    this.dropdownComponent = new MentionDropdown();
    this.currentQuery = '';
    this.selectedIndex = -1;
    this.users = [];
    this.mentionStartPos = null;
    this.isActive = false;
    this.observer = null;
    this.blockListenerControllers = new Set();
    
    // Configuration options
    this.options = {
      apiEndpoint: options.apiEndpoint || '/api/search-users/',
      minChars: options.minChars || 1,
      maxResults: options.maxResults || 10,
      debounceDelay: options.debounceDelay || 300,
      ...options
    };

    this.debounceTimer = null;
    this.init();
  }

  init() {
    this.editorElement = this.resolveEditorElement();

    if (!this.editorElement) {
      console.error('Editor not initialized properly');
      return;
    }

    this.editorElement.addEventListener('mention-selected', (e) => {
      const username = e?.detail?.username;
      if (username) {
        this.selectUserByUsername(username);
      }
    });

    // Use MutationObserver to watch for new editable blocks added to the DOM
    this.observer = new MutationObserver(() => {
      this.attachListenersToBlocks();
    });
    
    this.observer.observe(this.editorElement, {
      childList: true,
      subtree: true,
      attributes: false
    });

    // Attach listeners to any existing blocks
    setTimeout(() => this.attachListenersToBlocks(), 100);
  }

  /**
   * Attach input listeners to all contenteditable blocks
   */
  attachListenersToBlocks() {
    const editorElement = this.resolveEditorElement();
    if (!editorElement) {
      console.error('Editor element not found for mention handler');
      return;
    }
    
    // Find all contenteditable elements (the actual editable blocks)
    const editableElements = editorElement.querySelectorAll('[contenteditable="true"]');
    
    editableElements.forEach((element) => {
      // Only attach if not already attached
      if (!element.dataset.mentionHandlerAttached) {
        const controller = new AbortController();
        const { signal } = controller;

        element.addEventListener('input', (e) => this.handleInput(e), { signal });
        element.addEventListener('keydown', (e) => this.handleKeyDown(e), { signal });
        element.addEventListener('blur', () => this.dropdownComponent.hide(), { signal });

        this.blockListenerControllers.add(controller);
        element.dataset.mentionHandlerAttached = 'true';
      }
    });
  }

  resolveEditorElement() {
    if (this.editorElement) {
      return this.editorElement;
    }

    const holderId = this.options.holderId || this.editor?.configuration?.holder || this.editor?.config?.holder;
    if (typeof holderId === 'string') {
      this.editorElement = document.getElementById(holderId);
      if (this.editorElement) {
        return this.editorElement;
      }
    }

    if (this.editor?.holder instanceof HTMLElement) {
      this.editorElement = this.editor.holder;
      return this.editorElement;
    }

    return document.querySelector('.codex-editor') || null;
  }

  /**
   * Handle input in editor blocks
   */
  handleInput(e) {
    const element = e.target;
    const text = element.textContent || '';
    const selection = window.getSelection();
    
    if (!selection.rangeCount) {
      this.closeMentionDropdown();
      return;
    }

    // Get the cursor position within this element
    const range = selection.getRangeAt(0);
    const preCaretRange = range.cloneRange();
    preCaretRange.selectNodeContents(element);
    preCaretRange.setEnd(range.endContainer, range.endOffset);
    const cursorPos = preCaretRange.toString().length;
    this.activeElement = element;
    this.activeCursorPos = cursorPos;
    
    // Check if we're after an @ symbol
    const textBeforeCursor = text.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    
    if (lastAtIndex === -1) {
      this.closeMentionDropdown();
      return;
    }

    // Check if @ is at the beginning of a word (after space or at start)
    if (lastAtIndex > 0 && !/\s/.test(text[lastAtIndex - 1])) {
      this.closeMentionDropdown();
      return;
    }

    const queryStart = lastAtIndex + 1;
    const query = textBeforeCursor.substring(queryStart);

    // Only trigger if query has minimum characters or is just "@"
    if (query.length === 0 && text[lastAtIndex] === '@') {
      // Show dropdown even with empty query
      this.currentQuery = '';
      this.mentionStartPos = lastAtIndex;
      this.showEmptyState();
      return;
    }

    this.currentQuery = query;
    this.mentionStartPos = lastAtIndex;
    
    // Debounce the search
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.searchUsers(query);
    }, this.options.debounceDelay);
  }

  /**
   * Handle keyboard navigation in dropdown
   */
  handleKeyDown(e) {
    if (!this.isActive || !this.dropdownComponent || !this.dropdownComponent.isOpen()) {
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this.dropdownComponent.selectNextItem();
        break;
      case 'ArrowUp':
        e.preventDefault();
        this.dropdownComponent.selectPrevItem();
        break;
      case 'Enter':
        {
          const active = this.dropdownComponent.selectActiveItem();
          if (active && active.username) {
            e.preventDefault();
            this.selectUserByUsername(active.username);
          }
        }
        break;
      case 'Escape':
        e.preventDefault();
        this.dropdownComponent.hide();
        break;
    }
  }

  /**
   * Show empty state when user types @ but no results yet
   */
  showEmptyState() {
    const rect = this.getEditorCursorRect();
    this.dropdownComponent.show([
      { __message: 'Start typing to search...' }
    ], this.editorElement, rect);
    this.isActive = true;
  }

  /**
   * Search for users by query
   */
  async searchUsers(query) {
    if (!query) {
      this.showEmptyState();
      return;
    }

    try {
      const response = await fetch(
        `${this.options.apiEndpoint}?query=${encodeURIComponent(query)}&limit=${this.options.maxResults}`,
        {
          headers: {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          }
        }
      );

      if (!response.ok) {
        console.error('User search failed:', response.statusText);
        this.closeMentionDropdown();
        return;
      }

      const data = await response.json();
      this.users = data.users || [];

      const rect = this.getEditorCursorRect();

      if (this.users.length === 0) {
        this.dropdownComponent.show([
          { __message: 'No users found' }
        ], this.editorElement, rect);
        return;
      }

      this.selectedIndex = 0;
      this.dropdownComponent.show(this.users, this.editorElement, rect);
      this.isActive = true;
    } catch (error) {
      this.dropdownComponent.show([
        { __message: 'Search error' }
      ], this.editorElement, this.getEditorCursorRect());
    }
  }

  /**
   * Show the mention dropdown
   */
  showMentionDropdown() {
    // Replaced by dropdown component
  }

  /**
   * Update dropdown items based on current users
   */
  updateDropdownItems() {
    // Handled by dropdown component
  }

  /**
   * Close the mention dropdown
   */
  closeMentionDropdown() {
    this.dropdownComponent.hide();
    this.isActive = false;
    this.selectedIndex = -1;
    this.users = [];
    this.currentQuery = '';
    this.mentionStartPos = null;
  }

  /**
   * Select the next user in dropdown
   */
  selectNext() {
    this.dropdownComponent.selectNextItem();
  }

  /**
   * Select the previous user in dropdown
   */
  selectPrevious() {
    this.dropdownComponent.selectPrevItem();
  }

  /**
   * Insert mention into editor
   */
  selectUser(user) {
    const element = this.activeElement;
    const cursorPos = this.activeCursorPos;
    const mentionStartPos = this.mentionStartPos;

    if (!element || typeof cursorPos !== 'number' || typeof mentionStartPos !== 'number') {
      this.closeMentionDropdown();
      return;
    }

    const text = element.textContent || '';

    // Get the before and after parts
    const beforeMention = text.substring(0, mentionStartPos);
    const afterQuery = text.substring(cursorPos);
    
    // Create the mention text with space after
    const mentionText = `@${user.username} `;
    const newText = beforeMention + mentionText + afterQuery;

    // Update the element's text
    this.clearElementContent(element);
    
    // Insert text nodes and create the new content
    const textNode = document.createTextNode(newText);
    element.appendChild(textNode);

    // Set cursor position after the mention
    const newCursorPos = beforeMention.length + mentionText.length;
    this.setCursorInElement(element, newCursorPos);

    // Trigger input event to update Editor.js
    element.dispatchEvent(new Event('input', { bubbles: true }));

    this.dropdownComponent.hide();
    this.activeElement = null;
    this.activeCursorPos = null;
  }

  /**
   * Select user by username (used when dropdown dispatches selection)
   */
  selectUserByUsername(username) {
    const user = this.users.find(u => u.username === username) || { username };
    this.selectUser(user);
  }

  /**
   * Get the cursor range bounding rect for dropdown placement
   */
  getEditorCursorRect() {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return null;
    try {
      const range = selection.getRangeAt(0);
      return range.getBoundingClientRect();
    } catch (e) {
      return null;
    }
  }

  /**
   * Clear element content (text only, preserving structure)
   */
  clearElementContent(element) {
    // Remove all child nodes
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }
  }

  /**
   * Set cursor position within an element
   */
  setCursorInElement(element, pos) {
    const selection = window.getSelection();
    const range = document.createRange();
    
    let currentPos = 0;
    let found = false;

    const traverse = (node) => {
      if (found) return;

      if (node.nodeType === 3) { // Text node
        const nextPos = currentPos + node.length;
        if (pos <= nextPos) {
          range.setStart(node, pos - currentPos);
          found = true;
          return;
        }
        currentPos = nextPos;
      } else {
        for (let i = 0; i < node.childNodes.length; i++) {
          traverse(node.childNodes[i]);
          if (found) return;
        }
      }
    };

    traverse(element);

    if (found) {
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
    }
  }

  /**
   * Destroy the mention handler
   */
  destroy() {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }

    this.blockListenerControllers.forEach((controller) => {
      controller.abort();
    });
    this.blockListenerControllers.clear();

    this.dropdownComponent.hide();
    clearTimeout(this.debounceTimer);
  }
}

export default MentionHandler;
