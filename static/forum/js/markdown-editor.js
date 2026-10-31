import { createMentionAutocomplete } from './mention-autocomplete.js';

let crepeModule;

function loadCrepe() {
    crepeModule ||= import('../vendor/crepe-entry.js');
    return crepeModule;
}

async function uploadImage(file, csrfToken) {
    const data = new FormData();
    data.append('image', file);
    const response = await fetch('/upload-image/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        credentials: 'same-origin',
        body: data,
    });
    const result = await response.json();
    if (!response.ok || result.success !== 1 || !result.file?.url) {
        throw new Error(result.error || 'Image upload failed');
    }
    return result.file.url;
}

export async function createMarkdownEditor({ holder, markdown = '', csrfToken = '' }) {
    const root = typeof holder === 'string' ? document.getElementById(holder) : holder;
    if (!root) throw new Error(`Editor holder ${holder} not found`);
    const { Crepe, editorViewCtx } = await loadCrepe();
    const crepe = new Crepe({
        root,
        defaultValue: markdown || '',
        features: {
            [Crepe.Feature.AI]: false,
            [Crepe.Feature.Table]: false,
        },
        featureConfigs: {
            [Crepe.Feature.BlockEdit]: {
                blockHandle: {
                    shouldShow: () => false,
                },
                textGroup: {
                    quote: null,
                    divider: null,
                },
                listGroup: {
                    taskList: null,
                },
            },
            [Crepe.Feature.ImageBlock]: {
                onUpload: (file) => uploadImage(file, csrfToken),
            },
        },
    });
    await crepe.create();
    const view = crepe.editor.action(ctx => ctx.get(editorViewCtx));
    const mentions = createMentionAutocomplete(view);
    return {
        save: async () => crepe.getMarkdown(),
        destroy: async () => {
            mentions.destroy();
            await crepe.destroy();
        },
    };
}

export class EditorManager {
    constructor() {
        this.editors = new Map();
    }

    async openEditor(id, markdown, csrfToken) {
        const existing = this.editors.get(id);
        if (existing) return existing;

        const root = document.getElementById(id);
        if (!root) throw new Error(`Editor holder ${id} not found`);

        const originalHTML = root.innerHTML;
        root.replaceChildren();
        try {
            const editor = await createMarkdownEditor({ holder: root, markdown, csrfToken });
            const activeEditor = { ...editor, root, originalHTML };
            this.editors.set(id, activeEditor);
            return activeEditor;
        } catch (error) {
            root.innerHTML = originalHTML;
            throw error;
        }
    }

    async closeEditor(id) {
        const editor = this.editors.get(id);
        if (!editor) return;
        await editor.destroy();
        editor.root.innerHTML = editor.originalHTML;
        this.editors.delete(id);
    }

    getEditor(id) {
        return this.editors.get(id);
    }
}
