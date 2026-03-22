export class SolutionInteractions {
    constructor() {
        try {
            this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            
            // Bind methods
            this.upvoteSolution = this.upvoteSolution.bind(this);
            this.downvoteSolution = this.downvoteSolution.bind(this);
            this.toggleAcceptSolution = this.toggleAcceptSolution.bind(this);
            
        } catch (error) {
            console.error("Error in SolutionInteractions constructor:", error);
            showMessage('Failed to initialize solution interactions', 'error');
        }
    }

    async upvoteSolution(solutionId) {
        try {
            const response = await fetch(`/solution/${solutionId}/upvote/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();
            
            // Handle messages from server
            if (data.messages) {
                data.messages.forEach(messageData => {
                    showMessage(messageData.message, messageData.tags);
                });
            }

            // Only update UI for successful votes
            if (response.ok && data.success) {
                this.updateVoteUI(solutionId, data);
            }
            
            return data;
        } catch (error) {
            console.error('Upvote error:', error);
            showMessage('Failed to upvote solution', 'error');
            // Don't rethrow - error is handled
        }
    }

    async downvoteSolution(solutionId) {
        try {
            const response = await fetch(`/solution/${solutionId}/downvote/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();
            
            // Handle messages from server
            if (data.messages) {
                data.messages.forEach(messageData => {
                    showMessage(messageData.message, messageData.tags);
                });
            }

            // Only update UI for successful votes
            if (response.ok && data.success) {
                this.updateVoteUI(solutionId, data);
            }
            
            return data;
        } catch (error) {
            console.error('Downvote error:', error);
            showMessage('Failed to downvote solution', 'error');
            // Don't rethrow - error is handled
        }
    }

    async toggleAcceptSolution(solutionId) {
        try {
            const response = await fetch(`/solution/${solutionId}/accept/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            console.log(data);
            
            // Handle messages from server
            if (data.messages) {
                data.messages.forEach(messageData => {
                    showMessage(messageData.message, messageData.tags);
                });
            }

            if (response.ok) {
                this.updateAcceptanceUI(solutionId, data);
            }
            
            return data;
        } catch (error) {
            console.error('Accept solution error:', error);
            showMessage('Failed to toggle solution acceptance', 'error');
            // Don't rethrow - error is handled
        }
    }

    updateVoteUI(solutionId, data) {
        const solutionContainer = document.querySelector(`[data-solution-id="${solutionId}"]`);
        if (!solutionContainer) return;

        // Update vote count
        const voteCount = solutionContainer.querySelector('.vote-count');
        if (voteCount) {
            voteCount.textContent = data.upvotes - data.downvotes;
        }

        // Update vote buttons state
        const upvoteButton = solutionContainer.querySelector('[data-vote-type="upvote"]');
        const downvoteButton = solutionContainer.querySelector('[data-vote-type="downvote"]');

        if (upvoteButton) {
            upvoteButton.classList.toggle('voted-up', data.vote_state === 'upvoted');
        }
        if (downvoteButton) {
            downvoteButton.classList.toggle('voted-down', data.vote_state === 'downvoted');
        }
    }

    updateAcceptanceUI(solutionId, data) {
        // Remove acceptance state from previously accepted solution
        if (data.previous_solution_id) {
            const prevSolution = document.querySelector(`[data-solution-id="${data.previous_solution_id}"]`);
            if (prevSolution) {
                prevSolution.classList.remove('accepted-solution');
                const prevAcceptButton = prevSolution.querySelector('.accept-solution-button');
                if (prevAcceptButton) {
                    prevAcceptButton.classList.remove('accept-button-accepted');
                    prevAcceptButton.classList.add('accept-button-unaccepted');
                }
            }
        }

        // Update current solution
        const currentSolution = document.querySelector(`[data-solution-id="${solutionId}"]`);
        if (currentSolution) {
            currentSolution.classList.toggle('accepted-solution', data.is_accepted);
            const acceptButton = currentSolution.querySelector('.accept-solution-button');
            if (acceptButton) {
                acceptButton.classList.toggle('accept-button-accepted', data.is_accepted);
                acceptButton.classList.toggle('accept-button-unaccepted', !data.is_accepted);
            }
        }
    }

    async toggleSaveSolution(solutionId) {
        try {
            const response = await fetch(`/save-solution/${solutionId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();
            
            // Handle messages from server
            if (data.messages) {
                data.messages.forEach(messageData => {
                    showMessage(messageData.message, messageData.tags);
                });
            }

            if (response.ok) {
                this.updateSaveUI(solutionId, data);
            }
            
            return data;
        } catch (error) {
            console.error('Save solution error:', error);
            showMessage('Failed to save solution', 'error');
            // Don't rethrow - error is handled
        }
    }

    updateSaveUI(solutionId, data) {
        const solutionContainer = document.querySelector(`[data-solution-id="${solutionId}"]`);
        if (!solutionContainer) return;

        const saveButton = solutionContainer.querySelector('.bookmark-button');
        if (saveButton) {
            saveButton.classList.toggle('active', data.saved);
            const icon = saveButton.querySelector('i');
            if (icon) {
                icon.className = data.saved ? 'fas fa-bookmark' : 'far fa-bookmark';
            }
            saveButton.title = data.saved ? 'Unsave' : 'Save';
        }
    }
}
