import { EditorManager } from './markdown-editor.js';

function addCommentContents(comments, contents) {
    for (const comment of comments || []) {
        contents.set(comment.id, comment.content);
        addCommentContents(comment.replies, contents);
    }
}

export class CommentEditor {
    constructor(solutions, csrfToken, editorManager = new EditorManager()) {
        this.editorManager = editorManager;
        this.csrfToken = csrfToken;
        this.contents = new Map();
        for (const solution of solutions) addCommentContents(solution.comments, this.contents);
        this.showReplyForm = this.showReplyForm.bind(this);
        this.submitComment = this.submitComment.bind(this);
        this.cancelComment = this.cancelComment.bind(this);
        this.saveCommentEdit = this.saveCommentEdit.bind(this);
        this.cancelCommentEdit = this.cancelCommentEdit.bind(this);
        this.toggleReplies = this.toggleReplies.bind(this);
        this.toggleRootComments = this.toggleRootComments.bind(this);
        this.bindEvents();
    }

    bindEvents() {
        document.addEventListener('click', (e) => {
            const button = e.target.closest('button'); 
            if (!button) return; // Ignore clicks outside buttons


            if (button.matches('.reply-button')) {
                const solutionId = Number(button.dataset.solutionId);
                const parentId = button.dataset.parentId || null;
                this.showReplyForm(solutionId, parentId);
            }
            if (button.matches('.edit-comment')) {
                const commentId = Number(button.dataset.commentId);
                this.showEditForm(commentId);
            }
            if (button.matches('.save-comment')) {
                const commentId = Number(button.dataset.commentId);
                this.saveCommentEdit(commentId);
            }
            if (button.matches('.cancel-comment')) {
                const commentId = Number(button.dataset.commentId);
                this.cancelCommentEdit(commentId);
            }
            if (button.matches('.delete-comment')) {
                const commentId = Number(button.dataset.commentId);
                this.deleteComment(commentId);
            }
            if (button.matches('.toggle-replies')) {
                const commentId = Number(button.dataset.commentId);
                this.toggleReplies(button, commentId);
            }
            if (button.matches('.toggle-root-comments')) {
                const solutionId = Number(button.dataset.solutionId);
                this.toggleRootComments(button, solutionId);
            }
        });
    }

    async showReplyForm(solutionId, parentId = null) {
        const formId = `comment-form-${solutionId}-${parentId || 'root'}`;
        const container = document.createElement('div');
        container.id = formId;
        container.className = 'comment-form-container';

        
        container.innerHTML = `
            <div id="editorjs-${formId}" class="markdown-editor comment-editor"></div>
            <div class="comment-actions">
                <button class="btn btn-primary btn-sm submit-comment">Submit</button>
                <button class="btn btn-secondary btn-sm cancel-comment">Cancel</button>
            </div>
        `;

        const target = parentId ? 
        document.querySelector(`#comment-${parentId} .replies`) :
        document.querySelector(`[data-solution-id="${solutionId}"] .comments`);
    
        if (!target) {
            console.error(`Could not find target container for solution ${solutionId}`);
            return;
        }
        
        target.appendChild(container);

        await this.editorManager.openEditor(`editorjs-${formId}`, '', this.csrfToken);

        container.querySelector('.submit-comment').addEventListener('click', () => 
            this.submitComment(solutionId, parentId, formId));
        container.querySelector('.cancel-comment').addEventListener('click', () => 
            this.cancelComment(formId));
    }

    async submitComment(solutionId, parentId, formId) {
        const editor = this.editorManager.getEditor(`editorjs-${formId}`);
        if (!editor) return;

        try {
            const content = await editor.save();
            const response = await fetch(`/comment/create/${solutionId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    content,
                    content_format: 'markdown',
                    parent_id: parentId
                })
            });

            const envelope = await response.json();
            if (envelope.message) showMessage(envelope.message, envelope.success ? 'success' : 'error');
            if (!response.ok || !envelope.success) throw new Error(envelope.message || 'Failed to create comment');
            await this.removeCommentForm(formId);
            this.refreshComments(solutionId);
        } catch (error) {
            console.error('Error submitting comment:', error);
        }
    }

    async cancelComment(formId) {
        await this.removeCommentForm(formId);
    }

    async removeCommentForm(formId) {
        await this.editorManager.closeEditor(`editorjs-${formId}`);
        const container = document.getElementById(formId);
        container?.remove();
    }

    async refreshComments(solutionId) {
        try {
            const response = await fetch(`/solution/${solutionId}/comments/`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to fetch comments');
            }
            
            const envelope = await response.json();
            if (!envelope.success) throw new Error(`${envelope.error_code || 'request_failed'}: ${envelope.message}`);
            const data = envelope.data;
            const commentsContainer = document.querySelector(`[data-solution-id="${solutionId}"] .comments`);

            console.log("DATA: ", data);
            
            if (commentsContainer) {
                // Update HTML
                commentsContainer.innerHTML = data.html;
                window.renderForumMath?.(commentsContainer);
                window.renderForumMentions?.(commentsContainer);
                
            
                // Initialize editors using the comments data
                if (data.comments && data.comments.length > 0) {
                    addCommentContents(data.comments, this.contents);
                }
            }
        } catch (error) {
            console.error('Error refreshing comments:', error);
        }
    }

    async showEditForm(commentId) {
        try {
            await this.editorManager.openEditor(
                `editorjs-comment-${commentId}`,
                this.contents.get(commentId),
                this.csrfToken,
            );
            this.toggleCommentActions(commentId, true);
        } catch (error) {
            console.error('Error enabling edit mode:', error);
        }
    }

    toggleCommentActions(commentId, isEditing) {
        const commentContainer = document.querySelector(`#comment-${commentId}`);
        if (!commentContainer) return;
    
        const defaultActions = commentContainer.querySelector('.default-actions');
        const editActions = commentContainer.querySelector('.edit-actions');
    
        if (defaultActions) {
            defaultActions.style.cssText = isEditing ? 'display: none !important;' : 'display: block !important;';
        }
        if (editActions) {
            editActions.style.cssText = isEditing ? 'display: block !important;' : 'display: none !important;';
        }
    }

    async saveCommentEdit(commentId) {
        const editor = this.editorManager.getEditor(`editorjs-comment-${commentId}`);
        if (!editor) return;

        try {
            const content = await editor.save();
            const response = await fetch(`/comment/edit/${commentId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ content, content_format: 'markdown' })
            });

            const data = await response.json();
            if (data.message) showMessage(data.message, data.success ? 'success' : 'error');


            if (response.ok && data.success) {
                window.location.reload();
            } else {
                console.error('Failed to save comment');
            }
        } catch (error) {
            console.error('Error saving comment:', error);
        }
    }

    async cancelCommentEdit(commentId) {
        try {
            await this.editorManager.closeEditor(`editorjs-comment-${commentId}`);
            this.toggleCommentActions(commentId, false);
        } catch (error) {
            console.error('Error canceling comment edit:', error);
        }
    }

    async deleteComment(commentId) {
        if (!confirm('Are you sure you want to delete this comment?')) {
            return;
        }
    
        try {
            const response = await fetch(`/comment/delete/${commentId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                }
            });
    
            const data = await response.json();
    
            if (data.message) showMessage(data.message, data.success ? 'success' : 'error');
    
            if (response.ok && data.success) {
                const commentContainer = document.querySelector(`#comment-${commentId}`);
                if (commentContainer) {
                    const solutionContainer = commentContainer.closest('[data-solution-id]');
                    const solutionId = solutionContainer?.dataset.solutionId;
                    
                    // Remove the comment from DOM
                    commentContainer.remove();
                    
                    if (solutionId) {
                        await this.refreshComments(solutionId);
                    }
                }
            }
        } catch (error) {
            console.error('Delete comment failed:', error);
            showMessage('Failed to delete comment', 'error');
        }
    }

    toggleReplies(button, commentId) {
        const comment = document.querySelector(`#comment-${commentId}`);
        const collapsedReplies = comment.querySelector('.collapsed-replies');
        
        if (collapsedReplies) {
            const isHidden = collapsedReplies.style.display === 'none';
            collapsedReplies.style.display = isHidden ? 'block' : 'none';
            button.textContent = isHidden ? 
                button.dataset.hideText : 
                button.dataset.showText;
        }
    }


    toggleRootComments(button, solutionId) {
        const container = button.closest('.root-comments');
        const collapsedComments = container.querySelector('.collapsed-root-comments');
        
        if (collapsedComments) {
            const isHidden = collapsedComments.style.display === 'none';
            collapsedComments.style.display = isHidden ? 'block' : 'none';
            button.textContent = isHidden ? 
                button.dataset.hideText : 
                button.dataset.showText;
        }
    }

}
