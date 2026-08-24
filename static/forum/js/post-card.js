const likedIcon = '<svg aria-label="Unlike" fill="currentColor" height="24" viewBox="0 0 48 48" width="24"><path d="M34.6 3.1c-4.5 0-7.9 1.8-10.6 5.6-2.7-3.7-6.1-5.5-10.6-5.5C6 3.1 0 9.6 0 17.6c0 7.3 5.4 12 10.6 16.5.6.5 1.3 1.1 1.9 1.7l2.3 2c4.4 3.9 6.6 5.9 7.6 6.5.5.3 1.1.5 1.6.5s1.1-.2 1.6-.5c1-.6 2.8-2.2 7.8-6.8l2-1.8c.7-.6 1.3-1.2 2-1.7C42.7 29.6 48 25 48 17.6c0-8-6-14.5-13.4-14.5z"></path></svg>';
const unlikedIcon = '<svg aria-label="Like" fill="currentColor" height="24" viewBox="0 0 24 24" width="24"><path d="M16.792 3.904A4.989 4.989 0 0 1 21.5 9.122c0 3.072-2.652 4.959-5.197 7.222-2.512 2.243-3.865 3.469-4.303 3.752-.477-.309-2.143-1.823-4.303-3.752C5.141 14.072 2.5 12.167 2.5 9.122a4.989 4.989 0 0 1 4.708-5.218 4.21 4.21 0 0 1 3.675 1.941c.84 1.175.98 1.763 1.12 1.763s.278-.588 1.11-1.766a4.17 4.17 0 0 1 3.679-1.938m0-2a6.04 6.04 0 0 0-4.797 2.127 6.052 6.052 0 0 0-4.787-2.127A6.985 6.985 0 0 0 .5 9.122c0 3.61 2.55 5.827 5.015 7.97.283.246.569.494.853.747l1.027.918a44.998 44.998 0 0 0 3.518 3.018 2 2 0 0 0 2.174 0 45.263 45.263 0 0 0 3.626-3.115l.922-.824c.293-.26.59-.519.885-.774 2.334-2.025 4.98-4.32 4.98-7.94a6.985 6.985 0 0 0-6.708-7.218Z"></path></svg>';

async function postCardRequest(button, url) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': button.dataset.csrf,
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin',
    });
    return response.json();
}

document.addEventListener('click', async (event) => {
    const card = event.target.closest('.card.clickable');
    if (!card) return;

    const copyButton = event.target.closest('.copy-link-button');
    if (copyButton) {
        event.preventDefault();
        const linkInput = copyButton.previousElementSibling;
        linkInput.select();
        document.execCommand('copy');
        const originalText = copyButton.textContent;
        copyButton.textContent = 'Copied!';
        setTimeout(() => { copyButton.textContent = originalText; }, 2000);
        return;
    }

    const followButton = event.target.closest('.follow-button');
    if (followButton) {
        event.preventDefault();
        const isFollowing = followButton.dataset.followed === 'true';
        const url = isFollowing ? followButton.dataset.unfollowUrl : followButton.dataset.followUrl;
        try {
            const data = await postCardRequest(followButton, url);
            if (data.success) {
                followButton.dataset.followed = data.followed.toString();
                followButton.querySelector('.follow-count').textContent = data.followers_count;
                followButton.classList.toggle('active', data.followed);
                const icon = followButton.querySelector('.follow-icon');
                icon.classList.toggle('bi-bell-fill', data.followed);
                icon.classList.toggle('bi-bell', !data.followed);
            }
        } catch (error) {
            console.error('Follow toggle failed:', error);
        }
        return;
    }

    const likeButton = event.target.closest('.like-button');
    if (likeButton) {
        event.preventDefault();
        const isLiked = likeButton.dataset.liked === 'true';
        const url = isLiked ? likeButton.dataset.unlikeUrl : likeButton.dataset.likeUrl;
        try {
            const data = await postCardRequest(likeButton, url);
            if (data.success) {
                likeButton.dataset.liked = data.liked.toString();
                likeButton.classList.toggle('active', data.liked);
                likeButton.querySelector('.like-count').textContent = data.like_count;
                likeButton.querySelector('.like-icon').innerHTML = data.liked ? likedIcon : unlikedIcon;
            }
        } catch (error) {
            console.error('Like toggle failed:', error);
        }
        return;
    }

    if (event.target.closest('a, button, input, textarea, select, .poll-display, .poll-container')) return;
    if (window.getSelection && window.getSelection().toString()) return;

    const url = card.dataset.postUrl;
    if (!url) return;
    const postIdMatch = url.match(/post\/(\d+)\//);
    if (postIdMatch) {
        sessionStorage.setItem('goBackUrl', window.location.pathname + window.location.search);
        sessionStorage.setItem('lastClickedPostId', postIdMatch[1]);
    }
    window.location.href = url;
});
