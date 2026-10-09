// static/forum/js/modules/solution-sorting.js

export class SolutionSorter {
    constructor() {
        this.currentSort = 'votes';
        this.postId = document.querySelector('#solutions-container').dataset.postId;
        this.initializeSortDropdown();
    }

    initializeSortDropdown() {
        const sortDropdown = document.getElementById('sortDropdown');
        const sortDropdownMenu = document.getElementById('sortDropdownMenu');
        const sortOptions = document.querySelectorAll('.sort-option');
        const currentSortText = document.getElementById('currentSort');

        if (!sortOptions.length || !currentSortText) {
            console.error("Sort elements not found in the DOM");
            return;
        }

        sortDropdown?.addEventListener('click', () => {
            sortDropdownMenu.classList.toggle('show');
        });

        sortOptions.forEach(option => {
            option.addEventListener("click", async (e) => {
                e.preventDefault();
                const innerSortOptions = document.querySelectorAll('.sort-option');
                innerSortOptions.forEach(opt => opt.classList.remove('active'));
                
                this.currentSort = option.getAttribute("data-sort");
                currentSortText.textContent = this.currentSort.charAt(0).toUpperCase() + this.currentSort.slice(1);
                
                await this.fetchAndRenderSolutions(this.currentSort);
                option.classList.add('active');
                sortDropdownMenu.classList.remove('show');
            });
        });

        this.fetchAndRenderSolutions(this.currentSort);
    }

    async fetchAndRenderSolutions(sortBy) {
        try {
            const response = await fetch(`solutions/sorted?sort=${sortBy}`);
            if (!response.ok) throw new Error('Failed to fetch solutions');
            
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(`${data.error_code || 'request_failed'}: ${data.message}`);
            
            this.updateSolutionsOrder(data.data.solutions);
        } catch (error) {
            console.error('Error fetching solutions:', error);
        }
    }

    updateSolutionsOrder(solutions) {
        const solutionsContainer = document.getElementById("solutions-container");
        if (!solutionsContainer) return;

        // Create a temporary container to store existing solution elements
        const existingSolutions = new Map();
        solutionsContainer.querySelectorAll('.solution-container').forEach(element => {
            const solutionId = element.dataset.solutionId;
            existingSolutions.set(solutionId, element);
        });

        // Clear the container
        solutionsContainer.innerHTML = '';

        // Reorder solutions based on the new order
        solutions.forEach(solution => {
            const solutionElement = existingSolutions.get(solution.id.toString());
            if (solutionElement) {
                solutionsContainer.appendChild(solutionElement);
            }
        });
    }
}
