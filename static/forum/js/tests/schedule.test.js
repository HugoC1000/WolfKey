const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'schedule.js'), 'utf8');

function openSchedule(today, tomorrow) {
    const ids = [
        'schedule-date-picker', 'prev-day', 'next-day', 'tomorrow-schedule',
        'today-schedule', 'schedule-title', 'schedule-badges', 'today-badges'
    ];
    const elements = Object.fromEntries(ids.map(id => [id, {
        value: '',
        innerHTML: '',
        textContent: id === 'schedule-title' ? "Tomorrow's Schedule" : '',
        dataset: { today, tomorrow },
        listeners: {},
        addEventListener(type, handler) { this.listeners[type] = handler; }
    }]));
    const requests = [];
    const document = {
        getElementById(id) { return elements[id]; },
        addEventListener(type, handler) {
            if (type === 'DOMContentLoaded') handler();
        }
    };
    vm.runInNewContext(source, {
        document,
        Date,
        WeakMap,
        Intl,
        Object,
        console,
        fetch(url) {
            return new Promise(resolve => requests.push({ url, resolve }));
        }
    });
    return { elements, requests };
}

async function resolveSchedule(request, block, date) {
    request.resolve({
        ok: true,
        async json() {
            return { success: true, data: {
                date,
                schedule: [{ block, time: '8:20-9:30' }]
            } };
        }
    });
    await new Promise(resolve => setImmediate(resolve));
}

test('late responses cannot replace the selected schedule', async () => {
    const { elements, requests } = openSchedule('2026-10-05', '2026-10-06');
    const picker = elements['schedule-date-picker'];
    picker.value = '2026-10-07';
    picker.listeners.change.call(picker);
    picker.value = '2026-10-08';
    picker.listeners.change.call(picker);

    await resolveSchedule(requests[3], 'Thursday', 'Thu, Oct 8');
    await resolveSchedule(requests[2], 'Wednesday', 'Wed, Oct 7');

    assert.match(elements['tomorrow-schedule'].innerHTML, /Thursday/);
    assert.doesNotMatch(elements['tomorrow-schedule'].innerHTML, /Wednesday/);
});

test('today response cannot change the selected date heading', async () => {
    const { elements, requests } = openSchedule('2026-10-04', '2026-10-05');
    await resolveSchedule(requests[1], 'Monday', 'Mon, Oct 5');
    await resolveSchedule(requests[0], 'Sunday', 'Sun, Oct 4');

    assert.equal(elements['schedule-title'].textContent, "Tomorrow's Schedule");
});

test('arrows advance calendar dates across daylight saving changes', () => {
    const { elements } = openSchedule('2026-03-08', '2026-03-09');
    const picker = elements['schedule-date-picker'];
    picker.value = '2026-03-08';
    elements['next-day'].listeners.click();
    assert.equal(picker.value, '2026-03-09');
    elements['prev-day'].listeners.click();
    assert.equal(picker.value, '2026-03-08');
});
