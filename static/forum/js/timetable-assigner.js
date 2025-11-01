import { CourseSelector } from '/static/forum/js/course-selector.js';

const BLOCK_CODES = ['1A','1B','1D','1E','2A','2B','2C','2D','2E'];

const selectors = [];

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
            onSelectionChange: (sel) => {
                // no-op for now
            }
        });

        // Default required flag
        selector.required = false;

        // Wire up the checkbox to toggle required flag
        const cb = document.getElementById(`required-${i}`);
        if (cb) {
            cb.addEventListener('change', () => {
                selector.required = cb.checked;
            });
        }

    selectors.push(selector);
    }
}

// Keep track of generated schedules
let schedulesCache = [];

async function requestSchedulesFromApi(selectedCourses) {
    // Call API to generate possible schedules for the selected courses
    try {
        const response = await fetch('/timetable/generate/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                requested_course_ids: selectedCourses.map(c => c.id),
                required_course_ids: collectRequiredCourseIds()
            })
        });

        const data = await response.json();
        if (!data.success) {
            alert('Error: ' + (data.error || 'Unknown error'));
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

        schedulesCache = normalized;
        renderScheduleCards(normalized);
    } catch (err) {
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
        requestSchedulesFromApi(actionable);
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
            <h5>Select courses and click "Evaluate Best Schedules"</h5>
            <p>We'll generate optimal schedule combinations for your selected courses.</p>
        </div>
    `;
    rc.appendChild(initialDiv);
    
    // Add block view
    renderStaticBlockView();
}

function renderStaticBlockView() {
    const rc = document.getElementById('result-container');
    
    // Add block view header and container
    const blockViewHeader = document.createElement('div');
    blockViewHeader.className = 'mb-3';
    blockViewHeader.innerHTML = `
        <h4>All Available Courses by Block. Use this to see what you can fill a blank space with</h4>
    `;
    rc.appendChild(blockViewHeader);
    
    // Create block view container
    const blockViewContainer = document.createElement('div');
    blockViewContainer.className = 'block-view-container card';
    
    const blockViewBody = document.createElement('div');
    blockViewBody.className = 'card-body p-3';
    
    // Fetch all courses and their block relationships
    fetchAllCoursesAndBlocks().then(blockCoursesData => {
        // For each block, show all courses that are available in it
        BLOCK_CODES.forEach(block => {
            const blockRow = document.createElement('div');
            blockRow.className = 'block-row d-flex align-items-center py-2 border-bottom';
            
            // Block label
            const blockLabel = document.createElement('div');
            blockLabel.className = 'block-label font-weight-bold text-primary';
            blockLabel.style.width = '60px';
            blockLabel.style.flexShrink = '0';
            blockLabel.textContent = block;
            
            // Courses container
            const coursesContainer = document.createElement('div');
            coursesContainer.className = 'courses-container flex-grow-1 ml-3';
            
            // Get all courses available in this block
            const coursesInBlock = blockCoursesData[block] || [];
            
            // Display courses as secondary badges
            if (coursesInBlock.length > 0) {
                coursesInBlock.forEach(courseName => {
                    const courseBadge = document.createElement('span');
                    courseBadge.className = 'badge badge-secondary mr-2 mb-1';
                    courseBadge.style.fontSize = '0.8rem';
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
            blockViewBody.appendChild(blockRow);
        });
    }).catch(error => {
        console.error('Error fetching block courses data:', error);
        // Fallback: show empty state
        const errorDiv = document.createElement('div');
        errorDiv.className = 'text-center text-muted p-3';
        errorDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Unable to load course data';
        blockViewBody.appendChild(errorDiv);
    });
    
    blockViewContainer.appendChild(blockViewBody);
    rc.appendChild(blockViewContainer);
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

    // If no selections were made, fallback to window.initialSelections (flattened)
    if (selected.length === 0 && window.initialSelections) {
        Object.values(window.initialSelections).forEach(v => {
            if (v && v.name && !/study/i.test(v.name)) selected.push(v);
        });
    }

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

function renderScheduleCards(schedules) {
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
        const noSchedulesDiv = document.createElement('div');
        noSchedulesDiv.className = 'card mb-3 schedules-section';
        noSchedulesDiv.innerHTML = `
            <div class="card-body text-center text-muted">
                <i class="fas fa-exclamation-triangle fa-3x mb-3"></i>
                <h5>No optimal schedules found</h5>
                <p>Unable to generate schedules that accommodate your selected courses.</p>
            </div>
        `;
        // Insert before the block view; support either <h4> or <h5> in template
        let blockViewHeader = rc.querySelector('h4');
        if (blockViewHeader && blockViewHeader.textContent.includes('All Available Courses')) {
            rc.insertBefore(noSchedulesDiv, blockViewHeader.parentElement);
        } else {
            rc.appendChild(noSchedulesDiv);
        }
        return;
    }

    // Create schedule section
    const scheduleSection = document.createElement('div');
    scheduleSection.className = 'schedules-section mb-4';
    
    // Create header
    const header = document.createElement('div');
    header.className = 'mb-2';
    header.innerHTML = `
        <h4>Generated Schedule Options (${schedules.length} options found)</h4>
    `;
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
        removeBtn.className = 'btn btn-sm btn-outline-danger';
        removeBtn.innerHTML = '&times;';
        removeBtn.title = 'Remove this schedule';
        removeBtn.addEventListener('click', () => {
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
            
            // Get course for this block from schedule
            const courseInBlock = getCourseForBlock(schedule, block);
            if (courseInBlock) {
                courseDiv.innerHTML = `<span class="text-primary">${courseInBlock}</span>`;
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
    
    let blockViewHeader = rc.querySelector('h4');
    if (blockViewHeader && blockViewHeader.textContent.includes('All Available Courses')) {
        rc.insertBefore(scheduleSection, blockViewHeader.parentElement);
    } else {
        rc.appendChild(scheduleSection);
    }
}

async function fetchAllCoursesAndBlocks() {
    try {
    const response = await fetch('/courses/all-courses-by-block', {
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
    } catch (error) {
        console.error('Error fetching all courses and blocks:', error);
        return {};
    }
}

function getCourseForBlock(schedule, block) {
    // Check if there's a mapping for this block
    if (schedule.mapping) {
        for (const [courseId, assignment] of Object.entries(schedule.mapping)) {
            if (assignment.block === block) {
                return assignment.course_name;
            }
        }
    }
    
    // Check if schedule has a blocks structure
    if (schedule.blocks && schedule.blocks[block] && schedule.blocks[block].length > 0) {
        return schedule.blocks[block][0]; // Take first course in block
    }
    
    return null;
}

function removeSchedule(index) {
    schedulesCache.splice(index, 1);
    renderScheduleCards(schedulesCache);
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

    document.getElementById('evaluate-btn').addEventListener('click', (e) => {
        e.preventDefault();
        evaluateSchedules();
    });
    
    // Initialize the block view on page load
    initializeBlockView();
}

window.addEventListener('DOMContentLoaded', init);
