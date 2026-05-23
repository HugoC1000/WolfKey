/**
 * Mention Handler for Editor.js
 * Handles @mentions and #course mentions with autocomplete dropdown
 * Also supports @everyone for admins
 */

import MentionDropdown from './mention-dropdown.js';

export class MentionHandler {
  constructor(editor, options = {}) {
    this.editor = editor;
    this.editorElement = null;
    this.dropdownComponent = new MentionDropdown();
    this.currentQuery = '';
    this.currentTrigger = null; // '@' for users, '#' for courses, '@' for everyone
    this.selectedIndex = -1;
    this.results = []; // Stores all results (users, courses, everyone)
    this.mentionStartPos = null;
    this.isActive = false;
    this.observer = null;
    this.blockListenerControllers = new Set();
    
    // Configuration options
    this.options = {
      apiEndpoint: options.apiEndpoint || '/mentions/search/',
      minChars: options.minChars || 1,
      maxResults: options.maxResults || 5,
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
      const mention = e?.detail;
      if (mention) {
        this.selectMention(mention);
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
    if (this.suppressNextInput) {
      this.suppressNextInput = false;
      return;
    }

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
    
    // Check if we're after an @ or # symbol
    const textBeforeCursor = text.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    const lastHashIndex = textBeforeCursor.lastIndexOf('#');
    
    // Determine which trigger (@  or #) we're working with
    let triggerIndex = -1;
    let trigger = null;
    
    if (lastAtIndex > lastHashIndex) {
      triggerIndex = lastAtIndex;
      trigger = '@';
    } else if (lastHashIndex >= 0) {
      triggerIndex = lastHashIndex;
      trigger = '#';
    }
    
    if (triggerIndex === -1) {
      this.closeMentionDropdown();
      return;
    }

    // Check if trigger is at the beginning of a word (after space or at start)
    if (triggerIndex > 0 && !/\s/.test(text[triggerIndex - 1])) {
      this.closeMentionDropdown();
      return;
    }

    // Only trigger if query has minimum characters or is just the trigger symbol
    const queryStart = triggerIndex + 1;
    const query = textBeforeCursor.substring(queryStart);

    // Stop mention search if there's a space in the query (user has moved on)
    // For '@' trigger we treat a space as the user moving on; for '#' (courses)
    // allow spaces so multi-word course names can be searched/selected.
    if (trigger === '@' && query.includes(' ')) {
      this.closeMentionDropdown();
      return;
    }

    if (query.length === 0 && text[triggerIndex] === trigger) {
      // Show dropdown even with empty query
      this.currentQuery = '';
      this.currentTrigger = trigger;
      this.mentionStartPos = triggerIndex;
      this.showEmptyState(trigger);
      return;
    }

    this.currentQuery = query;
    this.currentTrigger = trigger;
    this.mentionStartPos = triggerIndex;
    
    // Debounce the search
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.searchMentions(query, trigger);
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
          if (active) {
            e.preventDefault();
            this.selectMention(active);
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
   * Show empty state when user types @ or # but no results yet
   */
  showEmptyState(trigger) {
    const rect = this.getEditorCursorRect();
    this.dropdownComponent.show([
      { __message: `Start typing to search ${trigger === '@' ? 'users' : 'courses'}...` }
    ], this.editorElement, rect);
    this.isActive = true;
  }

  /**
   * Search for mentions (users, courses, everyone)
   */
  async searchMentions(query, trigger) {
    if (!query) {
      this.showEmptyState(trigger);
      return;
    }

    try {
      const url = `${this.options.apiEndpoint}?query=${encodeURIComponent(query)}&trigger=${encodeURIComponent(trigger)}&limit=${this.options.maxResults}`;
      const response = await fetch(url, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        }
      });

      if (!response.ok) {
        console.error(`[MentionHandler] Mention search failed: ${response.statusText}`);
        this.closeMentionDropdown();
        return;
      }

      const data = await response.json();
      
      // Filter results based on current trigger
      let filteredResults = [];
      
      if (trigger === '@') {
        // For @ trigger, show users and everyone
        filteredResults = [...(data.users || []), ...(data.everyone || [])];
      } else if (trigger === '#') {
        // For # trigger, show courses
        filteredResults = data.courses || [];
      }
      
      this.results = filteredResults;

      const rect = this.getEditorCursorRect();

      if (filteredResults.length === 0) {
        this.dropdownComponent.show([
          { __message: `No ${trigger === '@' ? 'users' : 'courses'} found` }
        ], this.editorElement, rect);
        return;
      }

      this.selectedIndex = 0;
      this.dropdownComponent.show(filteredResults, this.editorElement, rect);
      this.isActive = true;
    } catch (error) {
      console.error(`[MentionHandler] Search error:`, error);
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
   * Update dropdown items based on current results
   */
  updateDropdownItems() {
    // Handled by dropdown component
  }

  /**
   * Close the mention dropdown
   */
  closeMentionDropdown() {
    clearTimeout(this.debounceTimer);
    this.dropdownComponent.hide();
    this.isActive = false;
    this.selectedIndex = -1;
    this.results = [];
    this.currentQuery = '';
    this.currentTrigger = null;
    this.mentionStartPos = null;
  }

  /**
   * Select the next item in dropdown
   */
  selectNext() {
    this.dropdownComponent.selectNextItem();
  }

  /**
   * Select the previous item in dropdown
   */
  selectPrevious() {
    this.dropdownComponent.selectPrevItem();
  }

  /**
   * Insert mention into editor
   * Handles users, courses, and everyone mentions
   */
  selectMention(mention) {
    const element = this.activeElement;
    const cursorPos = this.activeCursorPos;
    const mentionStartPos = this.mentionStartPos;
    const trigger = this.currentTrigger;

    if (!element || typeof cursorPos !== 'number' || typeof mentionStartPos !== 'number' || !trigger) {
      this.closeMentionDropdown();
      return;
    }

    const text = element.textContent || '';

    // Get the before and after parts
    const beforeMention = text.substring(0, mentionStartPos);
    const afterQuery = text.substring(cursorPos);
    
    // Create the mention text with space after, based on mention type
    let mentionText = '';
    if (mention.type === 'user') {
      mentionText = `@${mention.username} `;
    } else if (mention.type === 'course') {
      // Use course ID with name to handle courses with spaces
      // Format: #course_id-coursename (ID is preserved for backend, name for display)
      mentionText = `#course_${mention.id}-${mention.name} `;
    } else if (mention.type === 'everyone') {
      mentionText = `@${mention.name} `;
    }
    
    const newText = beforeMention + mentionText + afterQuery;

    // Update the element's text
    this.clearElementContent(element);
    
    // Insert text nodes and create the new content
    const textNode = document.createTextNode(newText);
    element.appendChild(textNode);

    // Set cursor position after the mention
    const newCursorPos = beforeMention.length + mentionText.length;
    this.setCursorInElement(element, newCursorPos);

    // Close dropdown and reset handler state before triggering input
    this.closeMentionDropdown();

    // Trigger input event to update Editor.js
    this.suppressNextInput = true;
    element.dispatchEvent(new Event('input', { bubbles: true }));
  }

  /**
   * Select user by username (used when dropdown dispatches selection)
   * Legacy method - now uses selectMention
   */
  selectUserByUsername(username) {
    const user = this.results.find(u => u.username === username) || { username, type: 'user' };
    this.selectMention(user);
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
