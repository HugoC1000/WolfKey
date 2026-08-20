export function applyClassmateMatches(schedules, selectedPeople, schedulesByUserId) {
    const classmatesByCourseAndBlock = new Map();

    selectedPeople.forEach(user => {
        if (user.comparisonDisabled || user.scheduleUnavailable) return;
        const personSchedule = schedulesByUserId.get(Number(user.id));
        if (!personSchedule) return;

        Object.entries(personSchedule).forEach(([block, savedCourse]) => {
            if (!savedCourse?.course_id) return;
            const key = `${Number(savedCourse.course_id)}:${block}`;
            const classmates = classmatesByCourseAndBlock.get(key) || [];
            classmates.push({
                id: user.id,
                full_name: user.full_name || user.username,
                profile_picture_url: user.profile_picture_url,
            });
            classmatesByCourseAndBlock.set(key, classmates);
        });
    });

    schedules.forEach(schedule => {
        Object.entries(schedule.mapping || {}).forEach(([courseId, assignment]) => {
            const key = `${Number(courseId)}:${assignment.block}`;
            assignment.classmates = classmatesByCourseAndBlock.get(key) || [];
        });
    });

    return schedules;
}
