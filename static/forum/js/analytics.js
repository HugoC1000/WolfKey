/* Only visible product pages emit opens; fetches and DOM updates do not. */
(() => {
    const config = document.currentScript?.dataset;
    if (!config?.screen) return;
    const screen = config.screen;
    const uuid = () => {
        if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
        if (!globalThis.crypto?.getRandomValues) return null;
        return '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, c =>
            (c ^ globalThis.crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
    };
    const emit = (event_type) => {
        const id = uuid();
        if (!id) return;
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
        fetch('/api/analytics/events/', {
            method: 'POST', credentials: 'same-origin', keepalive: true,
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-WolfKey-Platform': 'web'},
            body: JSON.stringify({id, platform: 'web', event_type, screen}),
        }).then(response => {
            if (!response.ok) console.warn('Analytics event delivery failed', response.status);
        }).catch(() => console.warn('Analytics event delivery failed'));
    };
    window.wolfkeyAnalytics = {profileSearch: () => emit('profile_search')};
    let visible = false;
    const open = () => {
        if (visible || document.visibilityState !== 'visible') return;
        visible = true;
        emit('screen_open');
        if (screen === 'match') emit('match_open');
        if (screen === 'volunteer') emit('volunteer_open');
        if (screen === 'search' && config.profileSearch === 'true') emit('profile_search');
    };
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') visible = false;
        else open();
    });
    window.addEventListener('pagehide', () => { visible = false; });
    window.addEventListener('pageshow', open);
    open();
})();
