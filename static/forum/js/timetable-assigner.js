import { CourseSelector } from '/static/forum/js/course-selector.js';
import { UserSelector } from '/static/forum/js/user-selector.js';
import { applyClassmateMatches } from '/static/forum/js/atlas-classmate-matching.js';
import { getCSRFToken } from '/static/forum/js/utilities.js';

const BLOCK_CODES = ['1A','1B','1D','1E','2A','2B','2C','2D','2E'];

const selectors = [];
let selectedPeople = [];
const selectedPeopleSchedules = new Map();
const selectedPeopleScheduleRequests = new Map();
let userSelector = null;
let hasGeneratedResults = false;
let lastGeneratedInputSignature = null;
let resultsStale = false;
let isGenerating = false;
const blockCoursesCache = new Map();
let blockCourseRequestVersion = 0;

function createSelectors() {
    const container = document.getElementById('selectors-container');
    container.innerHTML = '';

    // Build a flat list of initial courses from window.initialSelections
    const initialList = [];
    if (window.initialSelections) {
        Object.values(window.initialSelections).forEach(v => {
            if (v && v.name && !/study/i.test(v.name)) initialList.push(v);
        });
    }

    // Create 9 unordered selectors; prefill them with initial courses arbitrarily
    for (let i = 0; i < 9; i++) {
        const wrapper = document.createElement('div');
        wrapper.className = 'selector-row';
        wrapper.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                <div id="selector-${i}" class="course-selector-root"></div>
                <div class="form-check form-check-inline ml-2 required-toggle">
                    <input class="form-check-input required-checkbox" type="checkbox" id="required-${i}">
                    <label class="form-check-label small text-muted" for="required-${i}">Required</label>
                </div>
            </div>
        `;
        container.appendChild(wrapper);

        const initial = initialList[i] ? [initialList[i]] : [];
        const selector = new CourseSelector({
            containerId: `selector-${i}`,
            formName: 'timetable-form',
            block: null,
            maxCourses: 1,
            initialSelection: initial,
            onSelectionChange: handleScheduleInputsChanged
        });

        // Default required flag
        selector.required = false;

        // Wire up the checkbox to toggle required flag
        const cb = document.getElementById(`required-${i}`);
        if (cb) {
            cb.addEventListener('change', () => {
                selector.required = cb.checked;
                handleScheduleInputsChanged();
            });
        }

    selectors.push(selector);
    }
}

// Keep track of generated schedules
let schedulesCache = [];

async function requestSchedulesFromApi(selectedCourses, options = {}) {
    // Call API to generate possible schedules for the selected courses
    const requestInputSignature = getCurrentInputSignature();
    isGenerating = true;
    updateFlowState();
    try {
        const response = await fetch('/timetable/generate/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify({
                requested_course_ids: selectedCourses.map(c => c.id),
                required_course_ids: collectRequiredCourseIds(),
            })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            alert('Error: ' + (data.error || 'Unable to generate schedules'));
            isGenerating = false;
            updateFlowState();
            return;
        }

        const requestedCourseNames = selectedCourses.map(c => (c.name || c.course_name || '')).filter(Boolean);
        const requestedCourseIds = selectedCourses.map(c => c.id).filter(Boolean);

        const normalized = (data.schedules || []).map((s, idx) => {
            const mapping = s.mapping || {};
            const blocks = s.blocks || {};
            const matched = s.matched_courses != null ? s.matched_courses : Object.keys(mapping).length;
            return Object.assign({}, s, {
                mapping,
                blocks,
                matchedCourses: matched,
                requestedCourseNames,
                requestedCourseIds,
                name: s.name || `Schedule Option ${idx + 1}`
            });
        });

        applyClassmateMatches(normalized, selectedPeople, selectedPeopleSchedules);
        schedulesCache = normalized;
        hasGeneratedResults = true;
        lastGeneratedInputSignature = requestInputSignature;
        resultsStale = getCurrentInputSignature() !== requestInputSignature;
        isGenerating = false;
        renderScheduleCards(normalized);
        updateFlowState();

        if (options.scrollToResults) {
            const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            document.getElementById('atlas-results-step')?.scrollIntoView({
                behavior: prefersReducedMotion ? 'auto' : 'smooth',
                block: 'start'
            });
        }
    } catch (err) {
        isGenerating = false;
        updateFlowState();
        console.error('Error generating schedules:', err);
        alert('Error generating schedules: ' + (err.message || err));
    }
}

function collectRequiredCourseIds() {
    const ids = [];
        selectors.forEach(sel => {
        try {
            if (sel.required) {
                const arr = sel.getSelectedCourses();
                if (arr && arr.length > 0) {
                    const c = arr[0];
                    if (c && c.id) ids.push(c.id);
                }
            }
        } catch (e) {
            // ignore
        }
    });
    // dedupe
    return Array.from(new Set(ids));
}

function evaluateSchedules() {
    const selected = collectSelectedCourses();
    const actionable = selected.filter(c => c && c.id && !/study/i.test(c.name));
    
    if (actionable.length === 0) {
        alert('Please select some courses first');
        return;
    }

        // Generate schedules based on selected courses instead of using predefined ones
        requestSchedulesFromApi(actionable, { scrollToResults: true });
}

function initializeBlockView() {
    const rc = document.getElementById('result-container');
    
    // Clear existing content and set up the block view
    rc.innerHTML = '';
    
    // Add initial message
    const initialDiv = document.createElement('div');
    initialDiv.className = 'card mb-3';
    initialDiv.id = 'initial-message';
    initialDiv.innerHTML = `
        <div class="card-body text-center text-muted">
            <i class="fas fa-search fa-3x mb-3"></i>
            <h5>Your schedule options will appear here</h5>
            <p>Choose courses, optionally add people, then generate your options.</p>
        </div>
    `;
    rc.appendChild(initialDiv);
    
    // Add block view
    renderStaticBlockView();
}

function renderStaticBlockView() {
    const rc = document.getElementById('result-container');
    
    const blockReference = document.createElement('section');
    blockReference.id = 'atlas-block-reference';
    blockReference.className = 'atlas-block-reference mb-3';

    const blockViewBody = document.createElement('div');
    blockViewBody.className = 'block-view-container';

    const blockReferenceHeader = document.createElement('div');
    blockReferenceHeader.className = 'atlas-block-reference-heading';

    const blockReferenceTitle = document.createElement('h5');
    blockReferenceTitle.textContent = 'Courses by block';
    blockReferenceHeader.appendChild(blockReferenceTitle);

    const blockFilter = document.createElement('fieldset');
    blockFilter.className = 'atlas-block-filter';

    const eligibleOption = createBlockFilterOption(
        'atlas-block-filter-eligible',
        'eligible',
        'Only show courses you can take',
        Boolean(window.atlasHasGradeLevel),
        !window.atlasHasGradeLevel
    );
    const allOption = createBlockFilterOption(
        'atlas-block-filter-all',
        'all',
        'Show all courses',
        !window.atlasHasGradeLevel,
        false
    );
    blockFilter.appendChild(eligibleOption);
    blockFilter.appendChild(allOption);

    if (!window.atlasHasGradeLevel) {
        const gradeGuidance = document.createElement('span');
        gradeGuidance.className = 'atlas-block-filter-guidance';
        gradeGuidance.textContent = 'Add your grade level in your profile to use this filter.';
        blockFilter.appendChild(gradeGuidance);
    }

    const blockRowsContainer = document.createElement('div');
    blockRowsContainer.className = 'atlas-block-rows';

    blockFilter.addEventListener('change', event => {
        if (event.target.name === 'atlas-block-filter') {
            loadBlockCourseRows(blockRowsContainer, event.target.value === 'eligible');
        }
    });

    blockReferenceHeader.appendChild(blockFilter);
    blockViewBody.appendChild(blockReferenceHeader);
    blockViewBody.appendChild(blockRowsContainer);
    loadBlockCourseRows(blockRowsContainer, Boolean(window.atlasHasGradeLevel));
    
    blockReference.appendChild(blockViewBody);
    rc.appendChild(blockReference);
}

function createBlockFilterOption(id, value, text, checked, disabled) {
    const label = document.createElement('label');
    label.className = `atlas-block-filter-option${disabled ? ' is-disabled' : ''}`;

    const input = document.createElement('input');
    input.type = 'radio';
    input.id = id;
    input.name = 'atlas-block-filter';
    input.value = value;
    input.checked = checked;
    input.disabled = disabled;

    const labelText = document.createElement('span');
    labelText.textContent = text;

    label.appendChild(input);
    label.appendChild(labelText);
    return label;
}

async function loadBlockCourseRows(container, eligibleOnly) {
    const requestVersion = ++blockCourseRequestVersion;
    container.replaceChildren();

    const loading = document.createElement('div');
    loading.className = 'atlas-block-loading text-muted';
    loading.textContent = 'Loading courses…';
    container.appendChild(loading);

    try {
        const cacheKey = eligibleOnly ? 'eligible' : 'all';
        let blockCoursesData = blockCoursesCache.get(cacheKey);
        if (!blockCoursesData) {
            blockCoursesData = await fetchAllCoursesAndBlocks(eligibleOnly);
            blockCoursesCache.set(cacheKey, blockCoursesData);
        }
        if (requestVersion !== blockCourseRequestVersion) return;
        container.replaceChildren();

        BLOCK_CODES.forEach(block => {
            const blockRow = document.createElement('div');
            blockRow.className = 'block-row d-flex align-items-center py-2 border-bottom';

            const blockLabel = document.createElement('div');
            blockLabel.className = 'block-label font-weight-bold text-primary';
            blockLabel.style.width = '60px';
            blockLabel.style.flexShrink = '0';
            blockLabel.textContent = block;

            const coursesContainer = document.createElement('div');
            coursesContainer.className = 'courses-container flex-grow-1 ml-3';
            const coursesInBlock = blockCoursesData[block] || [];

            if (coursesInBlock.length > 0) {
                coursesInBlock.forEach(courseName => {
                    const courseBadge = document.createElement('span');
                    courseBadge.className = 'atlas-course-pill';
                    courseBadge.textContent = courseName;
                    coursesContainer.appendChild(courseBadge);
                });
            } else {
                const emptyText = document.createElement('span');
                emptyText.className = 'text-muted';
                emptyText.style.fontSize = '0.9rem';
                emptyText.textContent = 'No courses available';
                coursesContainer.appendChild(emptyText);
            }

            blockRow.appendChild(blockLabel);
            blockRow.appendChild(coursesContainer);
            container.appendChild(blockRow);
        });
    } catch (error) {
        if (requestVersion !== blockCourseRequestVersion) return;
        console.error('Error fetching block courses data:', error);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'text-center text-muted p-3';
        errorDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Unable to load course data';
        container.replaceChildren(errorDiv);
    }
}

function collectSelectedCourses() {
    const selected = [];

    selectors.forEach(sel => {
        const arr = sel.getSelectedCourses();
        if (arr && arr.length > 0) {
            const c = arr[0];
            if (c && !/study/i.test((c.name || '').toString())) selected.push(c);
        }
    });

    // Deduplicate by id if present, otherwise by name
    const seen = new Set();
    const deduped = [];
    selected.forEach(c => {
        const key = (c.id ? `id_${c.id}` : `name_${(c.name||'').toLowerCase()}`);
        if (!seen.has(key)) {
            seen.add(key);
            deduped.push(c);
        }
    });

    return deduped;
}

function renderScheduleCards(schedules, options = {}) {
    const rc = document.getElementById('result-container');
    
    // Remove the initial message if it exists
    const initialMessage = document.getElementById('initial-message');
    if (initialMessage) {
        initialMessage.remove();
    }
    
    // Remove any existing schedule section
    const existingScheduleSection = document.querySelector('.schedules-section');
    if (existingScheduleSection) {
        existingScheduleSection.remove();
    }
    
    if (schedules.length === 0) {
        const optionsRemoved = options.emptyState === 'removed';
        const noSchedulesDiv = document.createElement('div');
        noSchedulesDiv.className = 'card mb-3 schedules-section';
        noSchedulesDiv.innerHTML = `
            <div class="card-body text-center text-muted">
                <i class="fas ${optionsRemoved ? 'fa-trash-alt' : 'fa-exclamation-triangle'} fa-3x mb-3"></i>
                <h5>${optionsRemoved ? 'All schedule options removed' : 'No optimal schedules found'}</h5>
                <p>${optionsRemoved
                    ? 'Generate again whenever you want a fresh set of options.'
                    : 'Unable to generate schedules that accommodate your selected courses.'}</p>
            </div>
        `;
        const blockReference = document.getElementById('atlas-block-reference');
        if (blockReference) {
            rc.insertBefore(noSchedulesDiv, blockReference);
        } else {
            rc.appendChild(noSchedulesDiv);
        }
        return;
    }

    // Create schedule section
    const scheduleSection = document.createElement('div');
    scheduleSection.className = 'schedules-section mb-4';
    
    // Keep the generated count quiet; the main section title is fixed above.
    const header = document.createElement('div');
    header.className = 'atlas-schedule-count mb-2';
    header.textContent = `${schedules.length} ${schedules.length === 1 ? 'option' : 'options'} found`;
    scheduleSection.appendChild(header);

    const scrollContainer = document.createElement('div');
    scrollContainer.className = 'schedules-scroll-container d-flex gap-3 pb-2 pt-2';
    scrollContainer.style.overflowX = 'auto';
    
    schedules.forEach((schedule, index) => {
        const card = document.createElement('div');
        card.className = 'schedule-card card';
        card.style.minWidth = '320px';
        card.style.maxWidth = '320px';
        card.style.flexShrink = '0';
        
        const cardHeader = document.createElement('div');
        cardHeader.className = 'card-header d-flex justify-content-between align-items-center';
        
        const titleDiv = document.createElement('div');
        titleDiv.innerHTML = `
            <h6 class="mb-0">Schedule ${index + 1}</h6>
            <small class="text-muted">${schedule.matched_courses || Object.keys(schedule.mapping || {}).length} courses assigned</small>
        `;
        
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'btn btn-sm btn-outline-danger';
        removeBtn.innerHTML = '&times;';
        removeBtn.title = 'Remove this schedule';
        removeBtn.setAttribute('aria-label', `Remove schedule ${index + 1}`);
        removeBtn.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            removeSchedule(index);
        });
        
        cardHeader.appendChild(titleDiv);
        cardHeader.appendChild(removeBtn);
        
        const cardBody = document.createElement('div');
        cardBody.className = 'card-body p-2';
        
        // Display complete schedule grid
        const scheduleGrid = document.createElement('div');
        scheduleGrid.className = 'schedule-grid';
        
    BLOCK_CODES.forEach(block => {
            const blockRow = document.createElement('div');
            blockRow.className = 'd-flex justify-content-between align-items-center py-1 border-bottom';
            
            const blockLabel = document.createElement('div');
            blockLabel.className = 'font-weight-bold';
            blockLabel.style.width = '30px';
            blockLabel.textContent = block;
            
            const courseDiv = document.createElement('div');
            courseDiv.className = 'flex-grow-1 ml-2';
            courseDiv.style.fontSize = '0.85rem';
            
            // Get course and exact-block classmate matches for this assignment.
            const assignment = getAssignmentForBlock(schedule, block);
            if (assignment) {
                const courseName = document.createElement('span');
                courseName.className = 'text-primary';
                courseName.textContent = assignment.course_name;
                courseDiv.appendChild(courseName);

                if (assignment.classmates.length > 0) {
                    const classmates = document.createElement('div');
                    classmates.className = 'atlas-classmates';
                    assignment.classmates.forEach((classmate, index) => {
                        classmates.appendChild(createClassmateChip(classmate, index));
                    });
                    courseDiv.appendChild(classmates);
                }
            } else {
                courseDiv.innerHTML = `<span class="text-muted">Blank (See other options below) </span>`;
            }
            
            blockRow.appendChild(blockLabel);
            blockRow.appendChild(courseDiv);
            scheduleGrid.appendChild(blockRow);
        });
        
        cardBody.appendChild(scheduleGrid);

        // Show missing courses (italic small text)
        const missingText = computeMissingText(schedule);
        if (missingText) {
            const miss = document.createElement('div');
            miss.className = 'text-muted small';
            miss.style.fontStyle = 'italic';
            miss.style.marginTop = '8px';
            miss.textContent = missingText;
            cardBody.appendChild(miss);
        }
        
        card.appendChild(cardHeader);
        card.appendChild(cardBody);
        scrollContainer.appendChild(card);
    });
    
    scheduleSection.appendChild(scrollContainer);
    
    const blockReference = document.getElementById('atlas-block-reference');
    if (blockReference) {
        rc.insertBefore(scheduleSection, blockReference);
    } else {
        rc.appendChild(scheduleSection);
    }
}

async function fetchAllCoursesAndBlocks(eligibleOnly = false) {
    const url = eligibleOnly
        ? '/courses/all-courses-by-block/?eligible_only=1'
        : '/courses/all-courses-by-block/';
    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    });

    if (!response.ok) {
        throw new Error('Failed to fetch course-block data');
    }

    const data = await response.json();
    return data.blocks || {};
}

function getAssignmentForBlock(schedule, block) {
    if (schedule.mapping) {
        for (const assignment of Object.values(schedule.mapping)) {
            if (assignment.block === block) {
                return {
                    course_name: assignment.course_name,
                    classmates: Array.isArray(assignment.classmates) ? assignment.classmates : []
                };
            }
        }
    }

    if (schedule.blocks && schedule.blocks[block] && schedule.blocks[block].length > 0) {
        const course = schedule.blocks[block][0];
        return {
            course_name: typeof course === 'string' ? course : course.name,
            classmates: []
        };
    }

    return null;
}

function createClassmateChip(classmate, index) {
    const chip = document.createElement('span');
    chip.className = 'atlas-classmate-chip';
    chip.tabIndex = 0;
    chip.title = classmate.full_name;
    chip.style.zIndex = String(index + 1);

    if (classmate.profile_picture_url) {
        const image = document.createElement('img');
        image.src = classmate.profile_picture_url;
        image.alt = classmate.full_name;
        image.className = 'atlas-classmate-avatar';
        chip.appendChild(image);
    }

    const name = document.createElement('span');
    name.className = 'atlas-classmate-name';
    name.textContent = classmate.full_name;
    chip.appendChild(name);
    return chip;
}

function initializePeopleSelector() {
    if (!window.atlasClassmateMatchingEnabled) return;

    userSelector = new UserSelector({
        containerId: 'user-selector-container',
        excludeUsers: [{ id: window.currentUserId }],
        searchParams: { include_schedule_comparison: '1' },
        isUserDisabled: user => user.schedule_comparison_enabled === false,
        getDisabledReason: () => 'Schedule comparison off',
        onUserSelect: (user) => {
            if (selectedPeople.some(selected => selected.id === user.id)) return;
            const selectedUser = { ...user, scheduleLoading: true };
            selectedPeople.push(selectedUser);
            updateSelectedPeopleDisplay();
            updateUserSelectorExclusions();
            updateFlowState();
            fetchAndCachePersonSchedule(selectedUser);
        }
    });
}

function updateUserSelectorExclusions() {
    if (!userSelector) return;
    userSelector.updateExcludeUsers([{ id: window.currentUserId }, ...selectedPeople]);
}

function updateSelectedPeopleDisplay() {
    const container = document.getElementById('selected-people');
    if (!container) return;
    container.innerHTML = '';

    selectedPeople.forEach(user => {
        const tag = document.createElement('span');
        tag.className = 'user-tag';
        if (user.comparisonDisabled || user.scheduleUnavailable) {
            tag.classList.add('atlas-person-disabled');
            tag.title = user.comparisonDisabled
                ? 'Schedule comparison off'
                : 'Schedule unavailable';
        }

        if (user.profile_picture_url) {
            const image = document.createElement('img');
            image.src = user.profile_picture_url;
            image.alt = '';
            image.className = 'atlas-selected-person-avatar';
            tag.appendChild(image);
        }

        const name = document.createElement('span');
        name.textContent = user.full_name || user.username;
        tag.appendChild(name);

        if (user.scheduleLoading) {
            const status = document.createElement('small');
            status.textContent = 'Loading schedule…';
            tag.appendChild(status);
        } else if (user.comparisonDisabled || user.scheduleUnavailable) {
            const status = document.createElement('small');
            status.textContent = user.comparisonDisabled
                ? 'Comparison off'
                : 'Schedule unavailable';
            tag.appendChild(status);
        }

        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.className = 'remove-btn atlas-person-remove';
        removeButton.setAttribute('aria-label', `Remove ${user.full_name || user.username}`);
        removeButton.textContent = '×';
        removeButton.addEventListener('click', () => {
            selectedPeople = selectedPeople.filter(selected => selected.id !== user.id);
            selectedPeopleSchedules.delete(Number(user.id));
            selectedPeopleScheduleRequests.delete(Number(user.id));
            refreshCachedScheduleClassmates();
            updateSelectedPeopleDisplay();
            updateUserSelectorExclusions();
            updateFlowState();
        });
        tag.appendChild(removeButton);
        container.appendChild(tag);
    });
}

async function fetchAndCachePersonSchedule(user) {
    const userId = Number(user.id);
    const requestToken = Symbol('person-schedule-request');
    selectedPeopleScheduleRequests.set(userId, requestToken);

    try {
        const response = await fetch(`/user-blocks/${user.id}/`);
        const data = await response.json();
        if (selectedPeopleScheduleRequests.get(userId) !== requestToken) return;

        if (!response.ok) {
            markPersonScheduleUnavailable(user.id, response.status === 403, requestToken);
            return;
        }

        if (!selectedPeople.some(selected => selected.id === user.id)) return;
        selectedPeopleScheduleRequests.delete(userId);
        selectedPeopleSchedules.set(userId, data.schedule || {});
        selectedPeople = selectedPeople.map(selected => (
            selected.id === user.id
                ? { ...selected, scheduleLoading: false, scheduleUnavailable: false }
                : selected
        ));
        updateSelectedPeopleDisplay();
        refreshCachedScheduleClassmates();
        updateFlowState();
    } catch (error) {
        if (selectedPeopleScheduleRequests.get(userId) !== requestToken) return;
        console.error('Unable to load selected person schedule:', error);
        markPersonScheduleUnavailable(user.id, false, requestToken);
    }
}

function markPersonScheduleUnavailable(userId, comparisonDisabled, requestToken) {
    const normalizedUserId = Number(userId);
    if (selectedPeopleScheduleRequests.get(normalizedUserId) !== requestToken) return;
    if (!selectedPeople.some(selected => selected.id === userId)) return;

    selectedPeopleScheduleRequests.delete(normalizedUserId);
    selectedPeopleSchedules.delete(normalizedUserId);
    selectedPeople = selectedPeople.map(selected => (
        selected.id === userId
            ? {
                ...selected,
                scheduleLoading: false,
                scheduleUnavailable: !comparisonDisabled,
                comparisonDisabled,
            }
            : selected
    ));
    updateSelectedPeopleDisplay();
    updateUserSelectorExclusions();
    refreshCachedScheduleClassmates();
    updateFlowState();
}

function refreshCachedScheduleClassmates() {
    if (!hasGeneratedResults || schedulesCache.length === 0) return;
    applyClassmateMatches(schedulesCache, selectedPeople, selectedPeopleSchedules);
    renderScheduleCards(schedulesCache);
}

function getCurrentInputSignature() {
    const courseIds = collectSelectedCourses()
        .map(course => String(course.id))
        .sort();
    const requiredIds = collectRequiredCourseIds()
        .map(String)
        .sort();
    return `${courseIds.join(',')}|required:${requiredIds.join(',')}`;
}

function handleScheduleInputsChanged() {
    resultsStale = hasGeneratedResults
        && getCurrentInputSignature() !== lastGeneratedInputSignature;
    updateFlowState();
}

function updateFlowState() {
    const courseCount = collectSelectedCourses().length;
    const activePeople = selectedPeople.filter(user => (
        !user.comparisonDisabled && !user.scheduleUnavailable
    )).length;
    const hasCourses = courseCount > 0;
    const resultsCurrent = hasGeneratedResults && !resultsStale;
    const activeStep = !hasCourses ? 1 : (isGenerating || resultsCurrent ? 3 : 2);

    document.querySelectorAll('[data-atlas-panel]').forEach(panel => {
        const panelNumber = Number(panel.dataset.atlasPanel);
        panel.classList.toggle('is-active', panelNumber === activeStep);
        panel.classList.toggle('is-complete', panelNumber < activeStep || (panelNumber === 2 && resultsCurrent));
        panel.classList.toggle('is-stale', panelNumber === 3 && resultsStale);
    });

    const courseCountElement = document.getElementById('atlas-course-count');
    if (courseCountElement) {
        courseCountElement.textContent = courseCount === 0
            ? 'No courses selected'
            : `${courseCount} course${courseCount === 1 ? '' : 's'} selected`;
    }

    const peopleCountElement = document.getElementById('atlas-people-count');
    if (peopleCountElement) {
        peopleCountElement.textContent = activePeople === 0
            ? 'No people selected'
            : `${activePeople} ${activePeople === 1 ? 'person' : 'people'} selected`;
    }

    const evaluateButton = document.getElementById('evaluate-btn');
    if (evaluateButton) {
        evaluateButton.disabled = !hasCourses || isGenerating;
        evaluateButton.classList.toggle(
            'is-ready',
            hasCourses && !isGenerating && !resultsCurrent
        );

        const buttonEyebrow = document.getElementById('evaluate-btn-eyebrow');
        const buttonLabel = document.getElementById('evaluate-btn-label');
        if (isGenerating) {
            buttonEyebrow.textContent = 'Working';
            buttonLabel.textContent = 'Generating options…';
        } else if (resultsStale) {
            buttonEyebrow.textContent = 'Courses changed';
            buttonLabel.textContent = 'Update schedule options';
        } else if (resultsCurrent) {
            buttonEyebrow.textContent = 'Generate a new set';
            buttonLabel.textContent = 'Find schedule options';
        } else if (hasCourses) {
            buttonEyebrow.textContent = 'Ready to generate';
            buttonLabel.textContent = 'Find schedule options';
        } else {
            buttonEyebrow.textContent = 'Add courses first';
            buttonLabel.textContent = 'Find schedule options';
        }
    }

    const actionStatus = document.getElementById('atlas-action-status');
    if (actionStatus) {
        if (!hasCourses) {
            actionStatus.textContent = 'Select at least one course to continue.';
        } else if (isGenerating) {
            actionStatus.textContent = 'Building your schedule options…';
        } else if (resultsStale) {
            actionStatus.textContent = 'Courses changed — regenerate to update the options.';
        } else if (resultsCurrent) {
            actionStatus.textContent = '';
        } else if (activePeople > 0) {
            actionStatus.textContent = `Ready with ${courseCount} course${courseCount === 1 ? '' : 's'} and ${activePeople} ${activePeople === 1 ? 'person' : 'people'}.`;
        } else {
            actionStatus.textContent = 'Get possible alternatives for your schedule';
        }
    }

}

function removeSchedule(index) {
    if (!Number.isInteger(index) || index < 0 || index >= schedulesCache.length) return;
    schedulesCache.splice(index, 1);
    renderScheduleCards(schedulesCache, {
        emptyState: schedulesCache.length === 0 ? 'removed' : undefined,
    });
    updateFlowState();
}

function computeMissingText(schedule) {
    // Determine which requested courses are not assigned in this schedule
    try {
        const requested = (schedule.requestedCourseNames || schedule.requested_course_names || []);
        // If requested is an array of objects with name, normalize
        const requestedNames = requested.map(r => (typeof r === 'string') ? r : (r.name || r.course_name || ''))
            .filter(Boolean);

        const assigned = [];
        if (schedule.mapping) {
            for (const [k, v] of Object.entries(schedule.mapping)) {
                if (v && v.course_name) assigned.push(v.course_name);
            }
        }

        const missing = requestedNames.filter(n => !assigned.includes(n));
        if (missing.length === 0) return null;
        return `Missing: ${missing.join(', ')}`;
    } catch (e) {
        return null;
    }
}



function init() {
    createSelectors();
    initializePeopleSelector();
    updateFlowState();

    document.getElementById('evaluate-btn').addEventListener('click', (e) => {
        e.preventDefault();
        evaluateSchedules();
    });
    
    // Initialize the block view on page load
    initializeBlockView();
}

window.addEventListener('DOMContentLoaded', init);
