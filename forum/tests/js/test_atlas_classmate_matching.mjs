import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const moduleSource = await readFile(
    new URL('../../../static/forum/js/atlas-classmate-matching.js', import.meta.url),
    'utf8',
);
const moduleUrl = `data:text/javascript;base64,${Buffer.from(moduleSource).toString('base64')}`;
const { applyClassmateMatches } = await import(moduleUrl);

const schedules = [{
    mapping: {
        10: { block: '1A', course_name: 'Shared Course' },
        11: { block: '1B', course_name: 'Other Course' },
    },
}];
const people = [
    { id: 1, full_name: 'Exact Match' },
    { id: 2, full_name: 'Wrong Block' },
    { id: 3, full_name: 'Wrong Course' },
    { id: 4, full_name: 'Disabled', comparisonDisabled: true },
];
const peopleSchedules = new Map([
    [1, { '1A': { course_id: 10 } }],
    [2, { '1B': { course_id: 10 } }],
    [3, { '1A': { course_id: 11 } }],
    [4, { '1A': { course_id: 10 } }],
]);

applyClassmateMatches(schedules, people, peopleSchedules);

assert.deepEqual(
    schedules[0].mapping[10].classmates.map(person => person.id),
    [1],
);
assert.deepEqual(schedules[0].mapping[11].classmates, []);

peopleSchedules.set(5, { '1A': { course_id: 10 } });
people.push({ id: 5, full_name: 'Second Match' });
applyClassmateMatches(schedules, people, peopleSchedules);
assert.deepEqual(
    schedules[0].mapping[10].classmates.map(person => person.id),
    [1, 5],
);
