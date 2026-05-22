/**
 * MentionDropdown
 * Handles rendering and managing the mention suggestion dropdown
 * Supports users, courses, and everyone mentions
 */
class MentionDropdown {
  constructor() {
    this.dropdownElement = null;
    this.isVisible = false;
  }

  /**
   * Show the dropdown with matching mentions
   * @param {Array} mentions - List of mention objects (users, courses, or everyone)
   * @param {HTMLElement} editorElement - The editor element to position dropdown relative to
   * @param {DOMRect|ClientRect|Object} cursorRect - Bounding rect of the cursor for dropdown placement
   */
  show(mentions, editorElement, cursorRect) {
    if (!mentions || mentions.length === 0) {
      this.hide();
      return;
    }

    // Remove existing dropdown
    this.hide();

    // Create dropdown container
    this.dropdownElement = document.createElement('div');
    this.dropdownElement.className = 'mention-dropdown';
    this.dropdownElement.setAttribute('role', 'listbox');
    this.dropdownElement.setAttribute('aria-label', 'Mention suggestions');
    
    // Build mention items
    let itemsHtml = '';
    
    mentions.forEach((mention, idx) => {
      
      // Handle messages (empty state, no results, errors)
      if (mention.__message) {
        itemsHtml += `
          <div class="mention-dropdown-item mention-dropdown-message" role="status" aria-live="polite">
            <div class="mention-dropdown-info">
              <div class="mention-dropdown-name">${this.escape(mention.__message)}</div>
            </div>
          </div>
        `;
        return;
      }

      // Default to user type if not specified (backward compatibility)
      const mentionType = mention.type || 'user';

      // Handle user mentions
      if (mentionType === 'user') {
        const profilePicUrl = (mention.profile_picture_url && mention.profile_picture_url !== 'null') 
          ? mention.profile_picture_url 
          : '/static/images/default-avatar.png';
        const fullName = mention.full_name || mention.username || 'Unknown';
        const username = mention.username || '';
        
        itemsHtml += `
          <div class="mention-dropdown-item mention-dropdown-user" role="option" aria-selected="false" tabindex="0" data-mention-type="user" data-username="${this.escape(username)}" data-user-id="${mention.id}">
            <img src="${this.escape(profilePicUrl)}" alt="" class="mention-dropdown-avatar" data-fallback-src="/static/images/default-avatar.png" onerror="this.src='/static/images/default-avatar.png'">
            <div class="mention-dropdown-info">
              <div class="mention-dropdown-name">${this.escape(fullName)}</div>
              <div class="mention-dropdown-username">@${this.escape(username)}</div>
            </div>
          </div>
        `;
        return;
      }

      // Handle course mentions
      if (mentionType === 'course') {        
        itemsHtml += `
          <div class="mention-dropdown-item mention-dropdown-course" role="option" aria-selected="false" tabindex="0" data-mention-type="course" data-course-name="${this.escape(mention.name)}" data-course-id="${mention.id}">
            <div class="mention-dropdown-course-icon">📚</div>
            <div class="mention-dropdown-info">
              <div class="mention-dropdown-name">${this.escape(mention.name)}</div>
              <div class="mention-dropdown-course-category">${this.escape(mention.category || 'Course')}</div>
            </div>
          </div>
        `;
        return;
      }

      // Handle "everyone" mention (admin only)
      if (mentionType === 'everyone') {        
        itemsHtml += `
          <div class="mention-dropdown-item mention-dropdown-everyone" role="option" aria-selected="false" tabindex="0" data-mention-type="everyone" data-everyone-name="${this.escape(mention.name)}">
            <div class="mention-dropdown-everyone-icon">👥</div>
            <div class="mention-dropdown-info">
              <div class="mention-dropdown-name">${this.escape(mention.name)}</div>
              <div class="mention-dropdown-everyone-note">Notify all users</div>
            </div>
          </div>
        `;
        return;
      }
      
      console.warn(`[MentionDropdown] Unknown mention type: ${mentionType}`, mention);
    });
    
    // If no items were rendered, something went wrong
    if (!itemsHtml || itemsHtml.trim().length === 0) {
      // Render error message
      itemsHtml = `
        <div class="mention-dropdown-item mention-dropdown-message" role="status" aria-live="polite">
          <div class="mention-dropdown-info">
            <div class="mention-dropdown-name">Error rendering mentions</div>
          </div>
        </div>
      `;
    }
    
    this.dropdownElement.innerHTML = itemsHtml;

      // Position and append next to the caret when possible.
      this.dropdownElement.style.position = 'fixed';
      this.dropdownElement.style.visibility = 'hidden';
      this.dropdownElement.style.left = '0px';
      this.dropdownElement.style.top = '0px';
      document.body.appendChild(this.dropdownElement);

      const rect = cursorRect || {};
      const dropdownRect = this.dropdownElement.getBoundingClientRect();
      const gap = 8;
      const viewportPadding = 8;
      const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;

      let left = (rect.right || rect.left || 0) + gap;
      let top = rect.top || 0;

      if (left + dropdownRect.width > viewportWidth - viewportPadding) {
        left = Math.max(viewportPadding, (rect.left || 0) - dropdownRect.width - gap);
      }

      if (top + dropdownRect.height > viewportHeight - viewportPadding) {
        top = Math.max(viewportPadding, viewportHeight - dropdownRect.height - viewportPadding);
      }

      this.dropdownElement.style.left = `${Math.max(viewportPadding, left)}px`;
      this.dropdownElement.style.top = `${Math.max(viewportPadding, top)}px`;
      this.dropdownElement.style.visibility = 'visible';

    this.isVisible = true;

    // Handle image fallbacks for user avatars
    this.dropdownElement.querySelectorAll('.mention-dropdown-avatar').forEach((img) => {
      img.addEventListener('error', () => {
        const fallback = img.dataset.fallbackSrc;
        if (fallback && img.getAttribute('src') !== fallback) {
          img.setAttribute('src', fallback);
        }
      }, { once: true });
    });

    // Add click handlers to items
    this.dropdownElement.querySelectorAll('.mention-dropdown-item:not(.mention-dropdown-message)').forEach(item => {
      item.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.dispatchMentionSelection(item, editorElement);
      });

      item.addEventListener('click', (e) => {
        e.stopPropagation();
        this.dispatchMentionSelection(item, editorElement);
      });
    });
    console.log('[MentionDropdown] Show method completed successfully');
  }

  /**
   * Dispatch mention selection event with appropriate data
   */
  dispatchMentionSelection(item, editorElement) {
    const mentionType = item.dataset.mentionType;
    let detail = { type: mentionType };

    if (mentionType === 'user') {
      detail = {
        type: 'user',
        username: item.dataset.username,
        userId: item.dataset.userId,
        full_name: item.querySelector('.mention-dropdown-name')?.textContent || '',
        profile_picture_url: item.querySelector('img')?.src || ''
      };
    } else if (mentionType === 'course') {
      detail = {
        type: 'course',
        name: item.dataset.courseName,
        id: item.dataset.courseId,
        category: item.querySelector('.mention-dropdown-course-category')?.textContent || ''
      };
    } else if (mentionType === 'everyone') {
      detail = {
        type: 'everyone',
        name: item.dataset.everyoneName
      };
    }

    const event = new CustomEvent('mention-selected', { detail });
    editorElement.dispatchEvent(event);
  }

  /**
   * Hide the dropdown
   */
  hide() {
    if (this.dropdownElement) {
      this.dropdownElement.remove();
      this.dropdownElement = null;
    }
    this.isVisible = false;
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
   * Check if dropdown is visible
   */
  isOpen() {
    return this.isVisible;
  }

  /**
   * Navigate to next item in dropdown (for keyboard support)
   */
  selectNextItem() {
    if (!this.dropdownElement) return;
    
    const items = this.dropdownElement.querySelectorAll('.mention-dropdown-item:not(.mention-dropdown-message)');
    const activeItem = this.dropdownElement.querySelector('.mention-dropdown-item.active');
    
    let nextIndex = 0;
    if (activeItem) {
      const currentIndex = Array.from(items).indexOf(activeItem);
      nextIndex = (currentIndex + 1) % items.length;
      activeItem.classList.remove('active');
      activeItem.setAttribute('aria-selected', 'false');
    }
    
    items[nextIndex].classList.add('active');
    items[nextIndex].setAttribute('aria-selected', 'true');
    items[nextIndex].focus();
  }

  /**
   * Navigate to previous item in dropdown (for keyboard support)
   */
  selectPrevItem() {
    if (!this.dropdownElement) return;
    
    const items = this.dropdownElement.querySelectorAll('.mention-dropdown-item:not(.mention-dropdown-message)');
    const activeItem = this.dropdownElement.querySelector('.mention-dropdown-item.active');
    
    let prevIndex = items.length - 1;
    if (activeItem) {
      const currentIndex = Array.from(items).indexOf(activeItem);
      prevIndex = (currentIndex - 1 + items.length) % items.length;
      activeItem.classList.remove('active');
      activeItem.setAttribute('aria-selected', 'false');
    }
    
    items[prevIndex].classList.add('active');
    items[prevIndex].setAttribute('aria-selected', 'true');
    items[prevIndex].focus();
  }

  /**
   * Select the currently active item
   */
  selectActiveItem() {
    if (!this.dropdownElement) return null;
    
    const activeItem = this.dropdownElement.querySelector('.mention-dropdown-item.active');
    if (activeItem) {
      const mentionType = activeItem.dataset.mentionType;
      
      if (mentionType === 'user') {
        return {
          type: 'user',
          username: activeItem.dataset.username,
          userId: activeItem.dataset.userId
        };
      } else if (mentionType === 'course') {
        return {
          type: 'course',
          name: activeItem.dataset.courseName,
          id: activeItem.dataset.courseId
        };
      } else if (mentionType === 'everyone') {
        return {
          type: 'everyone',
          name: activeItem.dataset.everyoneName
        };
      }
    }
    return null;
  }
}

export default MentionDropdown;
