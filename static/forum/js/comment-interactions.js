export class CommentInteractions {
    constructor(csrfToken) {
        this.csrfToken = csrfToken;
        document.addEventListener('click', (event) => {
            const button = event.target.closest('.comment-vote-button');
            if (button) this.vote(button);
        });
    }

    async vote(button) {
        const { commentId, voteType } = button.dataset;
        const response = await fetch(`/comment/${commentId}/${voteType}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': this.csrfToken, 'Content-Type': 'application/json' },
        });
        const data = await response.json();
        if (data.message) showMessage(data.message, data.success ? 'success' : 'error');
        if (!response.ok || !data.success) return;
        const result = data.data;
        const comment = document.querySelector(`#comment-${commentId}`);
        comment.querySelector('.comment-upvotes').textContent = result.upvotes;
        comment.querySelector('.comment-downvotes').textContent = result.downvotes;
        comment.querySelector('[data-vote-type="upvote"]').classList.toggle('voted-up', result.vote_state === 'upvoted');
        comment.querySelector('[data-vote-type="downvote"]').classList.toggle('voted-down', result.vote_state === 'downvoted');
    }
}
