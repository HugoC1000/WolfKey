class CourseSelector {
    constructor(options) {
        this.containerId = options.containerId;

        this.maxCourses = options.maxCourses;
        this.onSelectionChange = options.onSelectionChange;
        this.selectedCourses = options.initialSelection || [];
        this.form = document.getElementById(options.formName);
        
        this.init();
    }

    init() {
        // Remove any existing course inputs when initializing
        this.clearExistingInputs();
        
        // Create and append the UI elements
        this.container = document.getElementById(this.containerId);
        this.container.innerHTML = `
            <div class="course-selector-wrapper">
                <input type="text" class="form-control search-box" placeholder="Search courses...">
                <div class="course-dropdown"></div>
                <div class="selected-courses"></div>
            </div>
        `;

        this.searchBox = this.container.querySelector('.search-box');
        this.dropdown = this.container.querySelector('.course-dropdown');
        this.selectedContainer = this.container.querySelector('.selected-courses');

        // Set up event listeners
        this.searchBox.addEventListener('input', () => this.fetchCourses());
        
        // Initial render of selected courses
        this.updateSelectedCourses();
    }

    clearExistingInputs() {
        const existingInputs = this.form.querySelectorAll('input[name="courses"]');
        existingInputs.forEach(input => input.remove());
    }

    async fetchCourses() {
        const query = this.searchBox.value.trim();

        if (query.length === 0) {
            this.dropdown.style.display = "none";
            return;
        }

        try {
            const response = await fetch(`/api/courses/?q=${query}`);
            const data = await response.json();
            
            this.dropdown.innerHTML = "";
            if (data.length > 0) {
                this.dropdown.style.display = "block";
                data.forEach(course => this.createDropdownItem(course));
            } else {
                this.dropdown.style.display = "none";
            }
        } catch (error) {
            console.error("Error fetching courses:", error);
        }
    }

    createDropdownItem(course) {
        const div = document.createElement("div");
        div.classList.add("dropdown-item");
        div.innerHTML = `
            <strong>${course.name}</strong>
            <br>
            <span>${course.category} • ${course.level}</span>
        `;
        div.addEventListener('click', () => this.addCourse(course));
        this.dropdown.appendChild(div);
    }

    addCourse(course) {
        if (this.selectedCourses.length >= this.maxCourses) return;
        
        if (!this.selectedCourses.some(c => c.id === course.id)) {
            this.selectedCourses.push(course);
            this.updateSelectedCourses();
            this.updateFormData();
        }
        
        this.searchBox.value = '';
        this.dropdown.style.display = 'none';
    }

    removeCourse(courseId) {
        this.selectedCourses = this.selectedCourses.filter(course => course.id !== courseId);
        this.updateSelectedCourses();
        this.updateFormData();
    }

    updateSelectedCourses() {
        this.selectedContainer.innerHTML = "";
        this.selectedCourses.forEach(course => {
            const courseTag = document.createElement("div");
            courseTag.classList.add("course-tag");
            courseTag.innerHTML = `
                ${course.name} 
                <span class="remove-btn">&times;</span>
            `;
            courseTag.querySelector('.remove-btn').addEventListener('click', 
                () => this.removeCourse(course.id)
            );
            this.selectedContainer.appendChild(courseTag);
        });
    }

    getSelectedCourses() {
        return this.selectedCourses;
    }

    updateFormData() {
        // Clear existing inputs first
        this.clearExistingInputs();

        // Add new inputs for each selected course
        this.selectedCourses.forEach(course => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'courses';
            input.value = course.id.toString();
            this.form.appendChild(input);
        });

        if (this.onSelectionChange) {
            this.onSelectionChange(this.selectedCourses);
        }
    }
}

export { CourseSelector };