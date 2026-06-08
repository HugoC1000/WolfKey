/**
 * Post Card Mention Renderer
 * Renders mentions in post card previews using shared MentionUtils
 */

import MentionUtils from './mention-utils.js';

document.addEventListener('DOMContentLoaded', () => {
    // Find all post card preview text elements and render mentions
    document.querySelectorAll('.post-card-text').forEach(element => {
        MentionUtils.renderElement(element);
    });
});
