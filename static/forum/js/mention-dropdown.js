/**
 * MentionDropdown
 * Handles rendering and managing the mention suggestion dropdown
 */
class MentionDropdown {
  constructor() {
    this.dropdownElement = null;
    this.isVisible = false;
  }

  /**
   * Show the dropdown with matching users
   * @param {Array} users - List of user objects with { id, username, full_name, profile_picture_url }
   * @param {HTMLElement} editorElement - The editor element to position dropdown relative to
   * @param {DOMRect|ClientRect|Object} cursorRect - Bounding rect of the cursor for dropdown placement
   */
  show(users, editorElement, cursorRect) {
    if (!users || users.length === 0) {
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
    
    // Build user items
    let itemsHtml = '';
    users.forEach((user) => {
      if (user.__message) {
        itemsHtml += `
          <div class="mention-dropdown-item mention-dropdown-message" role="status" aria-live="polite">
            <div class="mention-dropdown-info">
              <div class="mention-dropdown-name">${this.escape(user.__message)}</div>
            </div>
          </div>
        `;
        return;
      }

      const profilePicUrl = user.profile_picture_url || '/static/images/default-avatar.png';
      itemsHtml += `
        <div class="mention-dropdown-item" role="option" aria-selected="false" tabindex="0" data-username="${this.escape(user.username)}" data-user-id="${user.id}">
          <img src="${this.escape(profilePicUrl)}" alt="" class="mention-dropdown-avatar" data-fallback-src="/static/images/default-avatar.png">
          <div class="mention-dropdown-info">
            <div class="mention-dropdown-name">${this.escape(user.full_name)}</div>
            <div class="mention-dropdown-username">@${this.escape(user.username)}</div>
          </div>
        </div>
      `;
    });
    
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

    this.dropdownElement.querySelectorAll('.mention-dropdown-avatar').forEach((img) => {
      img.addEventListener('error', () => {
        const fallback = img.dataset.fallbackSrc;
        if (fallback && img.getAttribute('src') !== fallback) {
          img.setAttribute('src', fallback);
        }
      }, { once: true });
    });

    // Add click handlers to items
    this.dropdownElement.querySelectorAll('.mention-dropdown-item').forEach(item => {
      item.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const username = item.dataset.username;
        const event = new CustomEvent('mention-selected', {
          detail: { username }
        });
        editorElement.dispatchEvent(event);
      });

      item.addEventListener('click', (e) => {
        e.stopPropagation();
        const username = item.dataset.username;
        const event = new CustomEvent('mention-selected', { 
          detail: { username } 
        });
        editorElement.dispatchEvent(event);
      });
    });
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
    
    const items = this.dropdownElement.querySelectorAll('.mention-dropdown-item');
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
    
    const items = this.dropdownElement.querySelectorAll('.mention-dropdown-item');
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
      return {
        username: activeItem.dataset.username,
        userId: activeItem.dataset.userId
      };
    }
    return null;
  }
}

export default MentionDropdown;
