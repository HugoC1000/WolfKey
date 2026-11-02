import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { test } from 'node:test';

const source = readFileSync(new URL('../../../static/forum/js/analytics.js', import.meta.url), 'utf8');
function browser(screen, visibility = 'visible', profileSearch = 'false') {
    const listeners = {};
    const events = [];
    const document = {
        currentScript: {dataset: {screen, profileSearch}}, visibilityState: visibility,
        querySelector: () => ({content: 'csrf'}),
        addEventListener: (name, fn) => { listeners[name] = fn; },
    };
    const window = {addEventListener: (name, fn) => { listeners[name] = fn; }};
    runInNewContext(source, {document, window, crypto: {randomUUID: () => 'event-id'}, console,
        fetch: (_url, options) => { events.push(JSON.parse(options.body)); return Promise.resolve({ok: true}); }});
    return {events, listeners, document, window};
}

test('visible opens count initial visit, background return and history restore once each', () => {
    const b = browser('post_detail');
    assert.equal(b.events.length, 1);
    b.listeners.pageshow();
    b.listeners.visibilitychange();
    assert.equal(b.events.length, 1);
    b.document.visibilityState = 'hidden'; b.listeners.visibilitychange();
    b.document.visibilityState = 'visible'; b.listeners.visibilitychange();
    assert.equal(b.events.length, 2);
    b.listeners.pagehide(); b.listeners.pageshow(); b.listeners.visibilitychange();
    assert.equal(b.events.length, 3);
    assert.ok(b.events.every(e => e.screen === 'post_detail' && e.event_type === 'screen_open'));
});

test('background documents wait; Match, search and volunteer emit separate features', () => {
    const b = browser('match', 'hidden');
    assert.equal(b.events.length, 0);
    b.document.visibilityState = 'visible'; b.listeners.visibilitychange();
    assert.deepEqual(b.events.map(e => e.event_type), ['screen_open', 'match_open']);
    b.window.wolfkeyAnalytics.profileSearch();
    assert.equal(b.events.at(-1).event_type, 'profile_search');
    assert.deepEqual(browser('volunteer').events.map(e => e.event_type), ['screen_open', 'volunteer_open']);
    assert.equal(browser('search', 'visible', 'true').events.at(-1).event_type, 'profile_search');
});

test('untracked pages do not emit events', () => {
    assert.equal(browser('').events.length, 0);
});
