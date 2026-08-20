class CourseSelector {
    constructor(options) {
        this.containerId = options.containerId;
        this.block = options.block || null; 
        this.maxCourses = options.maxCourses;
        this.onSelectionChange = options.onSelectionChange;
        this.selectedCourses = options.initialSelection || [];
        this.form = document.getElementById(options.formName);

        this.init();
    }

    init() {
        this.clearExistingInputs();

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

        this.searchBox.addEventListener('input', () => this.fetchCourses());

        document.addEventListener('click', (event) => {
            const isClickInside = this.container.contains(event.target);
            if (!isClickInside) {
                this.dropdown.style.display = 'none';
            }
        });

        this.updateSelectedCourses();
    }

    clearExistingInputs() {
        const inputName = this.block ? `block_${this.block}` : 'courses';
        const existingInputs = this.form.querySelectorAll(`input[name="${inputName}"]`);
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
        const experiencedColor = course.experienced_count !== 0 ? '#07D500' : 'inherit';
        let experiencedHTML = '';
        if (course.experienced_count >= 3) {
            experiencedHTML = ` • <span style="color: ${experiencedColor};">${course.experienced_count} experienced users</span>`;
        }else{
            experiencedHTML = ` • <span style="color: ${experiencedColor};">3 experienced users</span>`;
        }

        div.innerHTML = `
        <strong>${course.name}</strong><br>
        <span>${course.category}${experiencedHTML}</span>
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

    setSelectedCourses(courses) {
        this.selectedCourses = Array.isArray(courses) ? courses.slice(0, this.maxCourses) : [];
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

    updateFormData() {
        this.clearExistingInputs();

        this.selectedCourses.forEach(course => {
            const input = document.createElement('input');
            input.type = 'hidden';
            if (this.block){
                input.name = `block_${this.block}`;
            }
            else{
                input.name = 'courses';
            }
            input.value = course.id.toString();
            input.setAttribute('block', this.block);
            this.form.appendChild(input);
        });

        if (this.selectedCourses.length === 0 && this.block) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = `block_${this.block}`;
            input.value = 'NOCOURSE';
            this.form.appendChild(input);
        }

        if (this.onSelectionChange) {
            this.onSelectionChange(this.selectedCourses);
        }
    }

    getSelectedCourses() {
        return this.selectedCourses;
    }
}

export { CourseSelector };
