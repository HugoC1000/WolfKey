/**
 * Schedule date picker and navigation functionality
 */
document.addEventListener('DOMContentLoaded', function () {
    const datePicker = document.getElementById('schedule-date-picker');
    const prevDayBtn = document.getElementById('prev-day');
    const nextDayBtn = document.getElementById('next-day');
    const tomorrowScheduleList = document.getElementById('tomorrow-schedule');
    const scheduleTitle = document.getElementById('schedule-title');
    const scheduleBadges = document.getElementById('schedule-badges');
    
    if (!datePicker || !prevDayBtn || !nextDayBtn || !tomorrowScheduleList || !scheduleTitle || !scheduleBadges) {
        // Schedule elements not found on this page, skip initialization
        return;
    }
    
    const tomorrowDate = datePicker.dataset.tomorrow;
    const initialTitle = scheduleTitle.textContent; // Store the initial server-rendered title
    
    // Clear cache: reset date picker to default tomorrow date on page load
    datePicker.value = tomorrowDate;

    function isDateInCurrentWeek(dateString) {
        const selectedDate = new Date(dateString);
        const today = new Date();
        
        // Get the start of the current week (Sunday)
        const startOfWeek = new Date(today);
        startOfWeek.setDate(today.getDate() - today.getDay());
        startOfWeek.setHours(0, 0, 0, 0);
        
        // Get the end of the current week (Saturday)
        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setDate(startOfWeek.getDate() + 6);
        endOfWeek.setHours(23, 59, 59, 999);
        
        return selectedDate >= startOfWeek && selectedDate <= endOfWeek;
    }

    function getDayName(dateString) {
        const date = new Date(dateString);
        const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        return days[date.getDay()];
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
        
        // Show loading state
        tomorrowScheduleList.innerHTML = '<li class="list-group-item"><div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading...</li>';
        scheduleBadges.innerHTML = '';
        
        // Fetch schedule for the selected date
        fetch(`/schedules/daily/${dateString}/`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    tomorrowScheduleList.innerHTML = `<li class="list-group-item text-danger">${data.error}</li>`;
                    return;
                }
                
                // Update title with formatted date if not tomorrow and not in current week
                if (dateString !== tomorrowDate && !isDateInCurrentWeek(dateString)) {
                    scheduleTitle.textContent = data.date;
                }
                
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
                scheduleBadges.innerHTML = badgesHTML;
                
                // Build schedule list
                let scheduleHTML = '';
                
                // Add schedule items
                if (data.schedule && data.schedule.length > 0) {
                    if (data.schedule[0] === "no school") {
                        scheduleHTML += '<li class="list-group-item"><p style="margin-bottom: 0px;">No School</p></li>';
                    } else {
                        data.schedule.forEach(item => {
                            scheduleHTML += `
                                <li class="list-group-item">
                                    <div class="d-flex justify-content-between align-items-center mb-1">
                                        <p style="margin-bottom: 0px;">${item.block}</p>
                                        ${item.time ? `<p style="margin-bottom: 0px;">${item.time}</p>` : ''}
                                    </div>
                                </li>
                            `;
                        });
                    }
                } else {
                    scheduleHTML += '<li class="list-group-item"><p style="margin-bottom: 0px;">Schedule unavailable</p></li>';
                }
                
                tomorrowScheduleList.innerHTML = scheduleHTML;
            })
            .catch(error => {
                console.error('Error fetching schedule:', error);
                tomorrowScheduleList.innerHTML = '<li class="list-group-item text-danger">Error loading schedule</li>';
            });
    }

    // Date picker change event
    datePicker.addEventListener('change', function() {
        updateSchedule(this.value);
    });

    // Previous day button
    prevDayBtn.addEventListener('click', function() {
        const currentDate = new Date(datePicker.value);
        currentDate.setDate(currentDate.getDate() - 1);
        const newDate = currentDate.toISOString().split('T')[0];
        datePicker.value = newDate;
        updateSchedule(newDate);
    });

    // Next day button
    nextDayBtn.addEventListener('click', function() {
        const currentDate = new Date(datePicker.value);
        currentDate.setDate(currentDate.getDate() + 1);
        const newDate = currentDate.toISOString().split('T')[0];
        datePicker.value = newDate;
        updateSchedule(newDate);
    });
});
