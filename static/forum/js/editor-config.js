import { MathLiveBlock } from './math-block.js';
const createEditor = (holder,initialData, csrfToken, isReadOnly = false, contentElementId = 'editorjs-content') => {
    console.log("Intial Data: ", initialData);
    return new EditorJS({
        holder: holder,  // The container where Editor.js will be initialized
        data: initialData,
        readOnly: isReadOnly,
        tools: {
            image: {
                class: ImageTool,
                config: {
                    endpoints: {
                        byFile: '/upload-image/', // URL to upload files
                    },
                    field: 'image', // The name of the field expected by the backend
                    additionalRequestHeaders: {
                        'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]').value
                    },
                    features: {
                        caption: 'optional',
                    }  
                }
            },
            header: {
                class: Header,
                shortcut: 'CMD+SHIFT+H',
                levels: [1,2, 3, 4],
                defaultLevel: 2
            },
            delimiter: {
                class: Delimiter,
                config: {
                    styleOptions: ['star', 'dash', 'line'],
                    defaultStyle: 'line',
                    lineWidthOptions: [8, 15, 25, 35, 50, 60, 100],
                    defaultLineWidth: 25,
                    lineThicknessOptions: [1, 2, 3, 4, 5, 6],
                    defaultLineThickness: 2,
                }
            },
            list: {
                class: EditorjsList,
                inlineToolbar: true,
                config: {
                    defaultStyle: 'unordered'
                },
            },
            code: editorJsCodeCup,
            inlineCode: {
                class: InlineCode,
            },
            math: MathLiveBlock
        },
        onReady: () => {
            console.log('Editor.js is ready!');
            document.querySelectorAll('math-field').forEach(mathField => {
                const tex = mathField.value;

                if (tex) {
                    const mathElement = new MathfieldElement();
                    mathElement.value = tex;


                    // If the editor is in read-only mode, set the math field to read-only
                    if (isReadOnly) {
                        mathElement.readOnly = true;
                    }

                    // Replace the placeholder math-field with the initialized MathfieldElement
                    mathField.replaceWith(mathElement);
                }
            });
        },
        onChange: async (api) => {
            try {
                const outputData = await api.saver.save();
                const blocks = outputData.blocks;

                // Check if the last block is a math block
                if (blocks.length > 0) {
                    const lastBlock = blocks[blocks.length - 1];
                    if (lastBlock.type === 'math') {
                        // Add a paragraph block after the math block
                        api.blocks.insert('paragraph', { text: 'Note: Have at least another block if a math block is used. Edit this msg once you understand. ' }, undefined, blocks.length);
                    }
                }

                const contentElement = document.getElementById(contentElementId);
                if (contentElement) {
                    contentElement.value = JSON.stringify(outputData);
                    console.log("Editor.js content saved");
                } else {
                    console.warn(`Content element with ID '${contentElementId}' not found`);
                }
            } catch (error) {
                console.error('Saving failed:', error);
            }
        },
        minHeight: 75,
    })
}

console.log('editor-config.js loaded');
export default createEditor;

