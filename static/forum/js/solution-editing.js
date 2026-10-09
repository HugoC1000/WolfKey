// static/forum/js/modules/solution-editing.js

export class SolutionEditor {
    constructor(editorManager, csrfToken) {
        this.editorManager = editorManager;
        this.csrfToken = csrfToken;
        this.originalContents = {};
        this.initializeDeleteHandlers();
    }

    initializeDeleteHandlers() {
        // Use event delegation for dynamic forms
        document.addEventListener('submit', (event) => {
            const form = event.target;
            if (form.classList.contains('delete-solution-form')) {
                event.preventDefault();
                this.handleDeleteSolution(form);
            }
        });
    }

    async showEditForm(solutionId) {
        try {
            await this.editorManager.toggleEditorReadOnly(solutionId, false);
            const editor = this.editorManager.getEditor(solutionId);
            if (editor) {
                const content = await editor.save();
                this.originalContents[solutionId] = content;
            }
            this.toggleSolutionActions(solutionId, true);
        } catch (error) {
            console.error('Error enabling edit mode:', error);
        }
    }

    async saveSolution(solutionId) {
        const editor = this.editorManager.getEditor(solutionId);
        if (!editor) return;

        try {
            const outputData = await editor.save();
            const editSolutionUrl = `/solution/${solutionId}/edit/`;

            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', this.csrfToken);
            formData.append('solution_id', solutionId);
            formData.append('content', JSON.stringify(outputData));

            const response = await fetch(editSolutionUrl, {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (data.message) showMessage(data.message, data.success ? 'success' : 'error');

            if (response.ok && data.success) {
                this.cancelEdit(solutionId, false);
            } else {
                console.error('Failed to save solution:', data.error_code, data.message);
            }
        } catch (error) {
            console.error('Failed to save edited solution:', error);
        }
    }

    async cancelEdit(solutionId, revert = true) {
        const editor = this.editorManager.getEditor(solutionId);
        if (editor && this.originalContents[solutionId] && revert) {
            // Restore original content
            await editor.render(this.originalContents[solutionId]);
        }
        this.editorManager.toggleEditorReadOnly(solutionId, true);
        this.toggleSolutionActions(solutionId, false);
    }

    toggleSolutionActions(solutionId, isEditing) {
        const container = document.querySelector(`#editorjs-solution-${solutionId}`);
        if (!container) return;

        const solutionContainer = container.closest('.solution-container');
        const defaultActions = solutionContainer?.querySelector('.default-actions');
        const editActions = solutionContainer?.querySelector('.edit-actions');
        if (defaultActions) {
            defaultActions.style.cssText = isEditing ? 'display: none !important;' : 'display: block !important;';
        }
        if (editActions) {
            editActions.style.cssText = isEditing ? 'display: block !important;' : 'display: none !important;';
        }
    }


    async handleDeleteSolution(form) {
        
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });

            const data = await response.json();

            if (data.message) showMessage(data.message, data.success ? 'success' : 'error');

            if (response.ok && data.success) {
                const solutionId = form.querySelector('input[name="solution_id"]').value;
                const solutionContainer = document.querySelector(`.solution-container[data-solution-id="${solutionId}"]`);
                
                if (solutionContainer) {
                    solutionContainer.remove();
                }
            } else if (!response.ok || !data.success) {
                console.error('Failed to delete solution:', data.error_code, data.message);
            }
        } catch (error) {
            console.error('Delete solution failed:', error);
            showMessage('Failed to delete solution', 'error');
        }
    }

}