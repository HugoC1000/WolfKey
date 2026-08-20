class UserSelector {
    constructor(options) {
        this.containerId = options.containerId;
        this.onUserSelect = options.onUserSelect; // Callback when a user is selected
        this.excludeUsers = options.excludeUsers || []; // Users to exclude from search (read-only)
        this.searchParams = options.searchParams || {};
        this.isUserDisabled = options.isUserDisabled || (() => false);
        this.getDisabledReason = options.getDisabledReason || (() => '');
        this.searchTimer = null;
        this.searchRequestId = 0;
        this.searchAbortController = null;
        
        this.init();
    }

    init() {
        this.container = document.getElementById(this.containerId);
        this.container.innerHTML = `
            <div class="user-selector-wrapper">
                <div class="position-relative">
                    <input type="text" class="form-control search-box" placeholder="Search users to add...">
                    <div class="user-dropdown"></div>
                </div>
            </div>
        `;

        this.searchBox = this.container.querySelector('.search-box');
        this.dropdown = this.container.querySelector('.user-dropdown');

        this.searchBox.addEventListener('input', () => this.handleSearchInput());

        document.addEventListener('click', (event) => {
            const isClickInside = this.container.contains(event.target);
            if (!isClickInside) {
                this.dropdown.style.display = 'none';
            }
        });
    }

    handleSearchInput() {
        clearTimeout(this.searchTimer);
        if (this.searchBox.value.trim().length === 0) {
            this.searchRequestId += 1;
            this.searchAbortController?.abort();
            this.dropdown.style.display = 'none';
            return;
        }
        this.searchTimer = setTimeout(() => this.searchUsers(), 180);
    }

    async searchUsers() {
        const query = this.searchBox.value.trim();

        if (query.length === 0) {
            this.dropdown.style.display = "none";
            return;
        }

        try {
            const requestId = ++this.searchRequestId;
            this.searchAbortController?.abort();
            this.searchAbortController = new AbortController();
            const params = new URLSearchParams({ query, ...this.searchParams });
            const response = await fetch(`/api/search-users/?${params.toString()}`, {
                signal: this.searchAbortController.signal,
            });
            if (!response.ok) {
                throw new Error('Unable to search users');
            }
            const data = await response.json();
            if (requestId !== this.searchRequestId) return;

            this.dropdown.innerHTML = "";
            const availableUsers = (data.users || []).filter(user =>
                !this.excludeUsers.some(excluded => Number(excluded.id) === Number(user.id))
            );
            if (availableUsers.length > 0) {
                this.dropdown.style.display = "block";
                availableUsers.forEach(user => this.createDropdownItem(user));
            } else {
                this.dropdown.style.display = "none";
            }
        } catch (error) {
            if (error.name === 'AbortError') return;
            console.error("Error searching users:", error);
            this.dropdown.style.display = 'none';
        }
    }

    createDropdownItem(user) {
        const div = document.createElement("div");
        div.classList.add("dropdown-item");
        const disabled = this.isUserDisabled(user);
        if (disabled) {
            div.classList.add('user-selector-item-disabled');
            div.setAttribute('aria-disabled', 'true');
        }
        
        // Handle profile picture with fallback
        const profilePicture = user.profile_picture_url;
        
        const fullName = user.full_name || user.username;
        
        div.innerHTML = `
            <div class="d-flex align-items-center">
                <!-- Profile Picture -->
                <div class="me-4">
                    <img 
                        src="${profilePicture}" 
                        alt="Profile Picture" 
                        class="profile-picture"
                        style="width: 30px; height: 30px; border-radius: 50%; object-fit: cover; cursor: pointer;"
                        id="profilePicture"
                    >
                </div>

                <!-- User Info -->
                <div class="flex-grow-1">
                    <p class="card-title mb-1">${fullName}</p>
                    ${disabled ? `<small class="text-muted">${this.getDisabledReason(user)}</small>` : ''}
                </div>
            </div>
        `;

        if (!disabled) {
            div.addEventListener('click', () => this.selectUser(user));
        }
        this.dropdown.appendChild(div);
    }

    selectUser(user) {
        // Fire callback to parent component
        if (this.onUserSelect) {
            this.onUserSelect(user);
        }

        // Clear search
        this.searchBox.value = '';
        this.dropdown.style.display = 'none';
    }

    // Method to update excluded users from parent component
    updateExcludeUsers(users) {
        this.excludeUsers = users || [];
    }

    // Method to clear search input
    clearSearch() {
        this.searchBox.value = '';
        this.dropdown.style.display = 'none';
    }
}

export { UserSelector };
