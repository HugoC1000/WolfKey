const BLOCKS = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E'];

const importState = {
    source: 'image',
    file: null,
    active: false,
    detectedBlocks: new Set(),
    unresolvedBlocks: new Set(),
    clearableBlocks: new Set(),
    clearingBlocks: new Set(),
};

const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

function setStatus(message = '', type = '') {
    const status = document.getElementById('profile-import-status');
    if (!status) return;
    status.textContent = message;
    status.classList.toggle('is-error', type === 'error');
    status.classList.toggle('is-success', type === 'success');
}

function setLoading(loading) {
    const button = document.getElementById('profile-import-process');
    button.disabled = loading;
    button.querySelector('.profile-import-button-label').hidden = loading;
    button.querySelector('.profile-import-button-loading').hidden = !loading;
}

function switchSource(source) {
    importState.source = source;
    document.querySelectorAll('.profile-import-tab').forEach((tab) => {
        const selected = tab.dataset.importSource === source;
        tab.classList.toggle('is-active', selected);
        tab.setAttribute('aria-selected', selected ? 'true' : 'false');
    });
    document.getElementById('profile-import-image-panel').hidden = source !== 'image';
    document.getElementById('profile-import-text-panel').hidden = source !== 'text';
    setStatus();
}

function selectFile(file) {
    const selectedFile = document.getElementById('profile-import-selected-file');
    importState.file = file || null;
    selectedFile.hidden = !file;
    selectedFile.textContent = file ? `${file.name} · ${(file.size / (1024 * 1024)).toFixed(1)} MB` : '';
}

async function parseResponse(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
    return data;
}

function updateImportStatus() {
    if (!importState.active) return;
    const unresolved = importState.unresolvedBlocks.size;
    if (unresolved) {
        setStatus(`${unresolved} detected ${unresolved === 1 ? 'course needs' : 'courses need'} review.`, 'error');
    } else {
        const clearing = importState.clearingBlocks.size;
        setStatus(
            `Schedule filled below${clearing ? `; ${clearing} missing ${clearing === 1 ? 'block will' : 'blocks will'} be cleared` : ''}. Review it, then click Save Courses.`,
            'success',
        );
    }
}

window.handleImportedScheduleSelection = (block, selectedCourses) => {
    if (!importState.active) return;
    const container = document.getElementById(`block_${block}_selector`);
    if (importState.detectedBlocks.has(block) && selectedCourses.length === 0) {
        importState.unresolvedBlocks.add(block);
        container.classList.add('schedule-import-needs-review');
    } else {
        importState.unresolvedBlocks.delete(block);
        container.classList.remove('schedule-import-needs-review');
    }
    if (selectedCourses.length > 0) {
        importState.clearingBlocks.delete(block);
        container.classList.remove('schedule-import-will-clear');
    } else if (importState.clearableBlocks.has(block)) {
        importState.clearingBlocks.add(block);
        container.classList.add('schedule-import-will-clear');
    }
    updateImportStatus();
};

function applyPreviewToProfile(data) {
    if (!window.courseSelectors || Object.keys(window.courseSelectors).length !== BLOCKS.length) {
        throw new Error('The schedule editor is still loading. Please try again.');
    }

    importState.active = true;
    importState.detectedBlocks = new Set();
    importState.unresolvedBlocks = new Set();
    importState.clearableBlocks = new Set();
    importState.clearingBlocks = new Set();

    data.blocks.forEach((row) => {
        const selector = window.courseSelectors[`block_${row.block}`];
        const container = document.getElementById(`block_${row.block}_selector`);
        const hadCourse = selector.selectedCourses.length > 0;
        container.classList.remove('schedule-import-needs-review', 'schedule-import-will-clear');

        if (row.extracted_name) importState.detectedBlocks.add(row.block);
        if (!row.course && row.extracted_name) {
            importState.unresolvedBlocks.add(row.block);
            container.classList.add('schedule-import-needs-review');
            selector.searchBox.placeholder = `Detected: ${row.extracted_name} — search to correct`;
        } else {
            selector.searchBox.placeholder = 'Search courses...';
        }
        if (!row.course && hadCourse) {
            importState.clearableBlocks.add(row.block);
            importState.clearingBlocks.add(row.block);
            container.classList.add('schedule-import-will-clear');
        }

        selector.setSelectedCourses(row.course ? [row.course] : []);
    });

    updateImportStatus();
    document.getElementById('blockCoursesForm').scrollIntoView({behavior: 'smooth', block: 'start'});
}

async function processImport() {
    const formData = new FormData();
    if (importState.source === 'image') {
        if (!importState.file) {
            setStatus('Choose a screenshot first.', 'error');
            return;
        }
        formData.append('image', importState.file);
    } else {
        const text = document.getElementById('profile-import-text').value.trim();
        if (!text) {
            setStatus('Paste your schedule text first.', 'error');
            return;
        }
        formData.append('text', text);
    }

    setLoading(true);
    setStatus('Reading courses and blocks…');
    try {
        const response = await fetch('/api/schedule-import/preview/', {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken()},
            body: formData,
        });
        applyPreviewToProfile(await parseResponse(response));
    } catch (error) {
        setStatus(error.message, 'error');
    } finally {
        setLoading(false);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const importCard = document.getElementById('profile-schedule-import-card');
    const importToggle = document.getElementById('profile-schedule-import-toggle');
    if (!importCard || !importToggle) return;

    importToggle.addEventListener('click', () => {
        const opening = importCard.hidden;
        importCard.hidden = !opening;
        importToggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
        importToggle.classList.toggle('btn-outline-primary', !opening);
        importToggle.classList.toggle('btn-primary', opening);
        if (opening) {
            importCard.querySelector('.profile-import-tab.is-active')?.focus({preventScroll: true});
        }
    });

    document.querySelectorAll('.profile-import-tab').forEach((tab) => {
        tab.addEventListener('click', () => switchSource(tab.dataset.importSource));
    });

    const fileInput = document.getElementById('profile-import-image');
    const dropZone = document.getElementById('profile-import-drop-zone');
    fileInput.addEventListener('change', () => selectFile(fileInput.files[0]));
    ['dragenter', 'dragover'].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.add('is-dragging');
    }));
    ['dragleave', 'drop'].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.remove('is-dragging');
    }));
    dropZone.addEventListener('drop', (event) => selectFile(event.dataTransfer.files[0]));
    document.getElementById('profile-import-process').addEventListener('click', processImport);
});
