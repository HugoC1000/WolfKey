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
        if (!response.ok) return;
        const comment = document.querySelector(`#comment-${commentId}`);
        comment.querySelector('.comment-upvotes').textContent = data.upvotes;
        comment.querySelector('.comment-downvotes').textContent = data.downvotes;
        comment.querySelector('[data-vote-type="upvote"]').classList.toggle('voted-up', data.vote_state === 'upvoted');
        comment.querySelector('[data-vote-type="downvote"]').classList.toggle('voted-down', data.vote_state === 'downvoted');
    }
}
