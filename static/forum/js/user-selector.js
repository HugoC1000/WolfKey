class UserSelector {
    constructor(options) {
        this.containerId = options.containerId;
        this.onUserSelect = options.onUserSelect; // Callback when a user is selected
        this.excludeUsers = options.excludeUsers || []; // Users to exclude from search (read-only)
        
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

        this.searchBox.addEventListener('input', () => this.searchUsers());

        document.addEventListener('click', (event) => {
            const isClickInside = this.container.contains(event.target);
            if (!isClickInside) {
                this.dropdown.style.display = 'none';
            }
        });
    }

    async searchUsers() {
        const query = this.searchBox.value.trim();

        if (query.length === 0) {
            this.dropdown.style.display = "none";
            return;
        }

        try {
            const response = await fetch(`/api/search-users/?query=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            this.dropdown.innerHTML = "";
            if (data.users.length > 0) {
                this.dropdown.style.display = "block";
                // Filter out excluded users
                const availableUsers = data.users.filter(user => 
                    !this.excludeUsers.some(excluded => excluded.id === user.id)
                );
                availableUsers.forEach(user => this.createDropdownItem(user));
            } else {
                this.dropdown.style.display = "none";
            }
        } catch (error) {
            console.error("Error searching users:", error);
        }
    }

    createDropdownItem(user) {
        const div = document.createElement("div");
        div.classList.add("dropdown-item");
        
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
                <div>
                    <p class="card-title mb-1">${fullName}</p>
                </div>
            </div>
        `;

        div.addEventListener('click', () => this.selectUser(user));
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
