const SEARCH_URL = '/mentions/search/';
const SEARCH_DELAY = 250;

function mentionAtCaret(view) {
    const { selection } = view.state;
    if (!selection.empty || !selection.$from.parent.isTextblock || selection.$from.parent.type.spec.code) {
        return null;
    }

    const before = selection.$from.parent.textBetween(0, selection.$from.parentOffset, '\ufffc', '\ufffc');
    const match = before.match(/(?:^|\s)([@#])([\w. -]{0,50})$/);
    if (!match || (match[1] === '@' && (match[2].includes(' ') || match[2].length > 40))) {
        return null;
    }

    const from = selection.from - match[1].length - match[2].length;
    return {
        trigger: match[1],
        query: match[2],
        from,
        to: selection.from,
        key: `${from}:${match[1]}:${match[2]}`,
    };
}

function mentionText(item) {
    if (item.type === 'user' && item.username) return `@${item.username} `;
    if (item.type === 'course' && item.id && item.name) {
        return `#course_${item.id}-${encodeURIComponent(item.name)} `;
    }
    if (item.type === 'everyone') return '@everyone ';
    return null;
}

class MentionAutocomplete {
    constructor(view) {
        this.view = view;
        this.current = null;
        this.dismissedKey = null;
        this.items = [];
        this.activeIndex = 0;
        this.timer = null;
        this.updateTimer = null;
        this.request = null;
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'mention-dropdown';
        this.dropdown.setAttribute('role', 'listbox');
        this.dropdown.setAttribute('aria-label', 'Mention suggestions');
        this.dropdown.hidden = true;
        document.body.appendChild(this.dropdown);

        this.onInput = () => {
            clearTimeout(this.updateTimer);
            this.updateTimer = setTimeout(() => this.update(), 0);
        };
        this.onKeyDown = (event) => this.handleKeyDown(event);
        this.onPositionChange = () => this.position();
        this.onOutsidePointer = event => {
            if (!this.view.dom.contains(event.target) && !this.dropdown.contains(event.target)) this.close();
        };
        view.dom.addEventListener('input', this.onInput);
        view.dom.addEventListener('keyup', this.onInput);
        view.dom.addEventListener('click', this.onInput);
        view.dom.addEventListener('compositionend', this.onInput);
        view.dom.addEventListener('keydown', this.onKeyDown, true);
        window.addEventListener('scroll', this.onPositionChange, true);
        window.addEventListener('resize', this.onPositionChange);
        document.addEventListener('pointerdown', this.onOutsidePointer);
    }

    update() {
        const next = mentionAtCaret(this.view);
        if (!next) {
            this.close();
            this.dismissedKey = null;
            return;
        }
        if (next.key === this.dismissedKey) return;
        this.dismissedKey = null;
        if (next.key === this.current?.key) {
            this.current = next;
            this.position();
            return;
        }

        this.close();
        this.current = next;
        if (!next.query.trim()) {
            this.showMessage(`Start typing to search ${next.trigger === '@' ? 'users' : 'courses'}`);
            return;
        }
        this.timer = setTimeout(() => this.search(next), SEARCH_DELAY);
    }

    async search(query) {
        const request = new AbortController();
        this.request = request;
        const params = new URLSearchParams({ query: query.query, trigger: query.trigger, limit: '5' });
        try {
            const response = await fetch(`${SEARCH_URL}?${params}`, {
                credentials: 'same-origin',
                headers: { Accept: 'application/json' },
                signal: request.signal,
            });
            const envelope = await response.json();
            if (!response.ok || !envelope.success) throw new Error(envelope.message || 'Mention search failed');
            if (this.current?.key !== query.key) return;

            const data = envelope.data || {};
            const results = query.trigger === '@'
                ? [...(data.users || []), ...(data.everyone || []).filter(
                    item => item.name?.toLowerCase().startsWith(query.query.toLowerCase()),
                )]
                : data.courses || [];
            this.showResults(results);
        } catch (error) {
            if (error.name !== 'AbortError' && this.current?.key === query.key) {
                this.showMessage('Could not search mentions');
            }
        }
    }

    showResults(results) {
        this.items = results.filter(item => mentionText(item));
        this.activeIndex = 0;
        this.dropdown.replaceChildren();
        if (!this.items.length) {
            this.showMessage('No mentions found');
            return;
        }

        this.items.forEach((item, index) => {
            const option = document.createElement('button');
            option.type = 'button';
            option.className = 'mention-dropdown-item';
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', String(index === this.activeIndex));

            if (item.type === 'user') {
                const avatar = document.createElement('img');
                const fallbackPicture = item.fallback_profile_picture_url || '/media/profile_pictures/default.png';
                avatar.className = 'mention-dropdown-avatar';
                avatar.alt = '';
                avatar.src = item.profile_picture_url || fallbackPicture;
                avatar.addEventListener('error', () => {
                    if (avatar.dataset.fallbackUsed) avatar.remove();
                    else {
                        avatar.dataset.fallbackUsed = 'true';
                        avatar.src = fallbackPicture;
                    }
                });
                option.appendChild(avatar);
            }

            const info = document.createElement('span');
            info.className = 'mention-dropdown-info';
            const name = document.createElement('span');
            name.className = 'mention-dropdown-name';
            name.textContent = item.type === 'user' ? item.full_name || item.username
                : item.type === 'course' ? item.name : '@everyone';
            info.appendChild(name);
            const detail = document.createElement('span');
            detail.className = 'mention-dropdown-username';
            detail.textContent = item.type === 'user' ? `@${item.username}`
                : item.type === 'course' ? item.category || 'Course' : 'Notify everyone';
            info.appendChild(detail);
            option.appendChild(info);
            option.addEventListener('mousedown', event => event.preventDefault());
            option.addEventListener('click', () => this.select(index));
            this.dropdown.appendChild(option);
        });
        this.dropdown.hidden = false;
        this.highlight();
        this.position();
    }

    showMessage(message) {
        this.items = [];
        this.dropdown.replaceChildren();
        const status = document.createElement('div');
        status.className = 'mention-dropdown-item mention-dropdown-message';
        status.setAttribute('role', 'status');
        status.textContent = message;
        this.dropdown.appendChild(status);
        this.dropdown.hidden = false;
        this.position();
    }

    position() {
        if (this.dropdown.hidden || !this.current) return;
        const caret = this.view.coordsAtPos(this.current.to);
        const width = this.dropdown.offsetWidth;
        const height = this.dropdown.offsetHeight;
        this.dropdown.style.left = `${Math.max(8, Math.min(caret.left, window.innerWidth - width - 8))}px`;
        this.dropdown.style.top = `${Math.max(8, Math.min(caret.bottom + 6, window.innerHeight - height - 8))}px`;
    }

    highlight() {
        for (const [index, option] of [...this.dropdown.children].entries()) {
            option.classList.toggle('active', index === this.activeIndex);
            option.setAttribute('aria-selected', String(index === this.activeIndex));
        }
    }

    handleKeyDown(event) {
        if (this.dropdown.hidden) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation();
            this.dismissedKey = this.current?.key;
            this.close();
            return;
        }
        if (!this.items.length) return;
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            event.stopPropagation();
            const direction = event.key === 'ArrowDown' ? 1 : -1;
            this.activeIndex = (this.activeIndex + direction + this.items.length) % this.items.length;
            this.highlight();
        } else if (event.key === 'Enter') {
            event.preventDefault();
            event.stopPropagation();
            this.select(this.activeIndex);
        }
    }

    select(index) {
        const item = this.items[index];
        const query = mentionAtCaret(this.view);
        if (!item || !query || query.key !== this.current?.key) {
            this.close();
            return;
        }
        this.view.dispatch(this.view.state.tr.insertText(mentionText(item), query.from, query.to));
        this.close();
        this.view.focus();
    }

    close() {
        clearTimeout(this.timer);
        clearTimeout(this.updateTimer);
        this.request?.abort();
        this.request = null;
        this.current = null;
        this.items = [];
        this.dropdown.hidden = true;
        this.dropdown.replaceChildren();
    }

    destroy() {
        this.close();
        clearTimeout(this.updateTimer);
        this.view.dom.removeEventListener('input', this.onInput);
        this.view.dom.removeEventListener('keyup', this.onInput);
        this.view.dom.removeEventListener('click', this.onInput);
        this.view.dom.removeEventListener('compositionend', this.onInput);
        this.view.dom.removeEventListener('keydown', this.onKeyDown, true);
        window.removeEventListener('scroll', this.onPositionChange, true);
        window.removeEventListener('resize', this.onPositionChange);
        document.removeEventListener('pointerdown', this.onOutsidePointer);
        this.dropdown.remove();
    }
}

export function createMentionAutocomplete(view) {
    return new MentionAutocomplete(view);
}
