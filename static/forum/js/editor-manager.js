// static/forum/js/editor-manager.js
import createEditor from './editor-config.js';
import MentionHandler from './mention-handler.js';
export class EditorManager {
    constructor() {
        this.editors = new Map();
        this.originalContents = {};
    }

    async initializeMainEditor(editorId, content, csrfToken, readOnly = true) {
        try {
            const editor = createEditor(editorId, content, csrfToken, readOnly);
            this.editors.set('main', editor);
            return editor;
        } catch (error) {
            console.error('Error initializing main editor:', error);
            throw error;
        }
    }

    async initializeSolutionEditors(solutions, csrfToken) {
        try {
            solutions.forEach(solution => {
                try {
                    const editor = createEditor(
                        `editorjs-solution-${solution.id}`,
                        solution.content,
                        csrfToken,
                        true
                    );
                    this.editors.set(solution.id, editor);
                } catch (solutionError) {
                    console.error(`Error initializing solution ${solution.id}:`, solutionError);
                }
            });
        } catch (error) {
            console.error('Error initializing solution editors:', error);
            throw error;
        }
    }

    async initializeCommentEditors(comments, csrfToken) {
        try {
            comments.forEach(comment => {
                try {
                    const editor = createEditor(
                        `editorjs-comment-${comment.id}`,
                        comment.content,
                        csrfToken,
                        true
                    );
                    this.editors.set(comment.id, editor);
                } catch (commentError) {
                    console.error(`Error initializing comment ${comment.id}:`, commentError);
                }
            });
        } catch (error) {
            console.error('Error initializing comment editors:', error);
            throw error;
        }
    }

    async initializeSolutionFormEditor(editorId, csrfToken, contentFieldId) {
        
        try {
            const editor = createEditor(
                editorId,
                {},
                csrfToken,
                false,
                contentFieldId
            );
            this.editors.set('solution-form', editor);
            return editor;
        } catch (error) {
            console.error('Error initializing solution form editor:', error);
            throw error;
        }
    }
    async initializeCommentFormEditor(editorId, csrfToken) {
        try {
            const editor = createEditor(
                editorId,
                {},
                csrfToken,
                false
            );
            this.editors.set(editorId, editor);
            return editor;
        } catch (error) {
            console.error('Error initializing comment form editor:', error);
            throw error;
        }
    }


    getEditor(id) {
        return this.editors.get(id);
    }

    toggleEditorReadOnly(editorId, readOnly) {
        const editor = this.getEditor(editorId);
        if (!editor) {
            console.warn(`Editor with ID '${editorId}' not found.`);
            return;
        }

        editor.readOnly.toggle(readOnly);

        if (!readOnly && !editor._mentionHandler) {
            const mentionOptions = editor._mentionHandlerOptions || {
                apiEndpoint: '/api/search-users/',
                minChars: 1,
                maxResults: 10,
                debounceDelay: 300,
                holderId: editorId,
            };
            editor._mentionHandler = new MentionHandler(editor, mentionOptions);
        }
    }

    async storeOriginalContent(commentId) {
        const editor = this.getEditor(commentId);
        if (!editor) return;

        try {
            const data = await editor.save();
            this.originalContents[commentId] = data;
        } catch (e) {
            console.error('Failed to store original content:', e);
        }
    }

    async restoreOriginalContent(commentId) {
        const editor = this.getEditor(commentId);
        const original = this.originalContents[commentId];
        if (!editor || !original) return;

        try {
            // Clear all blocks first
            await editor.blocks.clear();

            const output = await editor.save();
        
            // Re-insert original blocks
            for (const block of original.blocks) {
                await editor.blocks.insert(block.type, block.data);
            }
        } catch (e) {
            console.error('Failed to restore original content:', e);
        }
    }

}