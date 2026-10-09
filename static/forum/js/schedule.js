/**
 * Schedule date picker and navigation functionality
 */
document.addEventListener('DOMContentLoaded', function () {
    const datePicker = document.getElementById('schedule-date-picker');
    const prevDayBtn = document.getElementById('prev-day');
    const nextDayBtn = document.getElementById('next-day');
    const tomorrowScheduleList = document.getElementById('tomorrow-schedule');
    const todayScheduleList = document.getElementById('today-schedule');
    const scheduleTitle = document.getElementById('schedule-title');
    const scheduleBadges = document.getElementById('schedule-badges');
    const todayBadges = document.getElementById('today-badges');
    
    if (!datePicker || !prevDayBtn || !nextDayBtn || !tomorrowScheduleList || !scheduleTitle || !scheduleBadges) {
        // Schedule elements not found on this page, skip initialization
        return;
    }
    
    const tomorrowDate = datePicker.dataset.tomorrow;
    const todayDate = datePicker.dataset.today || getTodayDateISO();
    const initialTitle = scheduleTitle.textContent; // Store the initial server-rendered title
    const latestRequests = new WeakMap();
    
    // Clear cache: reset date picker to default tomorrow date on page load
    datePicker.value = tomorrowDate;
    
    // Helper function to get today's date in ISO format
    function getTodayDateISO() {
        const today = new Date();
        const parts = new Intl.DateTimeFormat('en-US', {
            timeZone: 'America/Vancouver', year: 'numeric', month: '2-digit', day: '2-digit'
        }).formatToParts(today);
        const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
        return `${values.year}-${values.month}-${values.day}`;
    }

    function isDateInCurrentWeek(dateString) {
        const selectedDate = new Date(`${dateString}T00:00:00Z`);
        const today = new Date(`${todayDate}T00:00:00Z`);
        
        // Get the start of the current week (Sunday)
        const startOfWeek = new Date(today);
        startOfWeek.setUTCDate(today.getUTCDate() - today.getUTCDay());
        
        // Get the end of the current week (Saturday)
        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setUTCDate(startOfWeek.getUTCDate() + 6);
        
        return selectedDate >= startOfWeek && selectedDate <= endOfWeek;
    }

    function getDayName(dateString) {
        const date = new Date(`${dateString}T00:00:00Z`);
        const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        return days[date.getUTCDay()];
    }

    function updateScheduleTitle(dateString) {
        // Check if the selected date is tomorrow
        if (dateString === tomorrowDate) {
            scheduleTitle.textContent = initialTitle;
        } else if (isDateInCurrentWeek(dateString)) {
            scheduleTitle.textContent = getDayName(dateString) + "'s Schedule";
        } else {
            // Will be updated with the formatted date from the API response
            scheduleTitle.textContent = "Schedule";
        }
    }

    function updateSchedule(dateString) {
        // Update title
        updateScheduleTitle(dateString);
        loadScheduleForDate(dateString, tomorrowScheduleList, scheduleBadges);
    }

    function loadScheduleForDate(dateString, scheduleContainer, badgesContainer) {
        // Load schedule for a specific date and render it into the given container.
        const requestId = (latestRequests.get(scheduleContainer) || 0) + 1;
        latestRequests.set(scheduleContainer, requestId);
        scheduleContainer.innerHTML = '<li class="list-group-item"><div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading...</li>';
        badgesContainer.innerHTML = '';

        fetch(`/schedules/daily/${dateString}/`)
            .then(async response => {
                const envelope = await response.json();
                if (!response.ok || !envelope.success) throw new Error(envelope.message || 'Failed to get schedule');
                return envelope.data;
            })
            .then(schedule => {
                if (latestRequests.get(scheduleContainer) !== requestId) return;
                renderScheduleData(schedule, scheduleContainer, badgesContainer, dateString);
            })
            .catch(error => {
                if (latestRequests.get(scheduleContainer) !== requestId) return;
                console.error('Error fetching schedule:', error);
                scheduleContainer.innerHTML = '<li class="list-group-item text-danger">Error loading schedule</li>';
            });
    }

    function renderScheduleData(data, scheduleContainer, badgesContainer, dateString) {
        // Render schedule data into the given containers.
        // Update title with formatted date if not tomorrow and not in current week
        if (scheduleContainer === tomorrowScheduleList && dateString !== tomorrowDate && !isDateInCurrentWeek(dateString)) {
            scheduleTitle.textContent = data.date;
        }

        const lunches = Array.isArray(data.community_lunches) ? data.community_lunches : [];

        // Build badges
        let badgesHTML = '';
        if (data.ceremonial_required) {
            badgesHTML += '<span class="badge rounded-pill schedule-badge-ceremonial"><i class="fas fa-user-tie me-1"></i>Ceremonial Uniform</span>';
        }
        if (data.early_dismissal) {
            badgesHTML += '<span class="badge rounded-pill schedule-badge-early"><i class="fas fa-clock me-1"></i>Early Dismissal</span>';
        }
        if (data.late_start) {
            badgesHTML += '<span class="badge rounded-pill schedule-badge-late"><i class="fas fa-coffee me-1"></i>Late Start</span>';
        }
        badgesContainer.innerHTML = badgesHTML;
        
        // Build schedule list
        let scheduleHTML = '';
        
        // Add schedule items
        if (data.schedule && data.schedule.length > 0) {
            if (data.schedule[0] === "no school") {
                scheduleHTML += '<li class="list-group-item"><p style="margin-bottom: 0px;">No School</p></li>';
            } else {
                let clubsRendered = false;
                data.schedule.forEach((item, index) => {
                    scheduleHTML += `
                        <li class="list-group-item">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <p style="margin-bottom: 0px;">${item.block}</p>
                                ${item.time ? `<p style="margin-bottom: 0px;">${item.time}</p>` : ''}
                            </div>
                        </li>
                    `;
                    if (index === 2 && lunches.length) {
                        scheduleHTML += buildClubsRow(lunches);
                        clubsRendered = true;
                    }
                });
                if (lunches.length && !clubsRendered) {
                    scheduleHTML += buildClubsRow(lunches);
                }
            }
        } else {
            scheduleHTML += '<li class="list-group-item"><p style="margin-bottom: 0px;">Schedule unavailable</p></li>';
        }
        
        scheduleContainer.innerHTML = scheduleHTML;
    }

    function buildClubsRow(lunches) {
        const pills = lunches.map(lunch => {
            const community = lunch.community || {};
            const name = escapeHtml(community.full_name || community.username || 'Community');
            const location = escapeHtml(lunch.location || 'Location TBD');
            const profileUrl = escapeHtml(lunch.profile_url || `/profile/${encodeURIComponent(community.username || '')}/`);
            return `<a class="badge rounded-pill schedule-badge-lunch text-decoration-none" href="${profileUrl}">${name} · ${location}</a>`;
        }).join('');
        return `<li class="list-group-item schedule-clubs-row">${pills}</li>`;
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>'"]/g, character => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
        }[character]));
    }

    // Date picker change event
    datePicker.addEventListener('change', function() {
        updateSchedule(this.value);
    });

    // Previous day button
    prevDayBtn.addEventListener('click', function() {
        const currentDate = new Date(`${datePicker.value}T00:00:00Z`);
        currentDate.setUTCDate(currentDate.getUTCDate() - 1);
        const newDate = currentDate.toISOString().split('T')[0];
        datePicker.value = newDate;
        updateSchedule(newDate);
    });

    // Next day button
    nextDayBtn.addEventListener('click', function() {
        const currentDate = new Date(`${datePicker.value}T00:00:00Z`);
        currentDate.setUTCDate(currentDate.getUTCDate() + 1);
        const newDate = currentDate.toISOString().split('T')[0];
        datePicker.value = newDate;
        updateSchedule(newDate);
    });

    // Load schedules asynchronously on page initialization
    loadScheduleForDate(todayDate, todayScheduleList, todayBadges);
    loadScheduleForDate(tomorrowDate, tomorrowScheduleList, scheduleBadges);
});
