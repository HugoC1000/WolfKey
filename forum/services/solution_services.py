from django.shortcuts import get_object_or_404
from forum.models import Post, Solution, SolutionUpvote, SolutionDownvote, SavedSolution
from forum.services.utils import detect_bad_words, extract_and_delete_files_from_content
from forum.services.notification_services import send_solution_notification_service
from django.db.models import F
import json

def create_solution_service(user, post_id, data):
    try:
        post = get_object_or_404(Post, id=post_id)
        
        if Solution.objects.filter(post=post, author=user).exists():
            return {'error': 'You have already submitted a solution'}

        content = data.get('content')
        if not content:
            return {'error': 'Content is required'}

        # Validate content
        if isinstance(content, dict) and 'blocks' in content:
            blocks = content.get('blocks', [])
            if (len(blocks) == 1 and 
                blocks[0].get('type') == 'paragraph' and 
                not blocks[0].get('data', {}).get('text', '').strip()) or len(blocks) == 0:
                return {'error': 'Solution cannot be empty'}

        detect_bad_words(content)
        
        solution = Solution.objects.create(
            post=post,
            author=user,
            content=content
        )
        if post.author != solution.author:
            send_solution_notification_service(solution)

        return {
            'id': solution.id,
            'message': 'Solution submitted successfully'
        }

    except ValueError as e:
        return {'error': str(e)}
    except Exception as e:
        return {'error': f'Error creating solution: {str(e)}'}

def update_solution_service(user, solution_id, data):
    try:
        
        solution = get_object_or_404(Solution, id=solution_id, author=user)
        content = data.get('content')
        
        if not content:
            return {'error': 'Content is required'}

        detect_bad_words(content)
        solution.content = content
        solution.save()

        return {
            'message': 'Solution updated successfully',
            'id': solution.id
        }
    except ValueError as e:
        return {'error': str(e)}
    except Exception as e:
        return {'error': f'Error updating solution: {str(e)}'}

def delete_solution_service(user, solution_id):
    try:
        solution = get_object_or_404(Solution, id=solution_id, author=user)
        
        # Extract and delete any files referenced in the solution content
        if solution.content:
            extract_and_delete_files_from_content(solution.content)
        
        solution.delete()
        return {'message': 'Solution deleted successfully'}
    except Exception as e:
        return {'error': str(e)}

def vote_solution_service(user, solution_id, vote_type):
    try:
        solution = get_object_or_404(Solution, id=solution_id)
        
        if vote_type == 'upvote':
            if SolutionDownvote.objects.filter(solution=solution, user=user).exists():
                SolutionDownvote.objects.filter(solution=solution, user=user).delete()
                solution.downvotes -= 1
                message = 'Downvote removed'
            elif not SolutionUpvote.objects.filter(solution=solution, user=user).exists():
                SolutionUpvote.objects.create(solution=solution, user=user)
                solution.upvotes += 1
                message = 'Solution upvoted successfully'
            else:
                return {
                    'conflict': True, 
                    'error': 'Already upvoted',
                    'messages': [{'message': 'You have already upvoted this solution', 'tags': 'info'}]
                }
        else:  # downvote
            if SolutionUpvote.objects.filter(solution=solution, user=user).exists():
                SolutionUpvote.objects.filter(solution=solution, user=user).delete()
                solution.upvotes -= 1
                message = 'Upvote removed'
            elif not SolutionDownvote.objects.filter(solution=solution, user=user).exists():
                SolutionDownvote.objects.create(solution=solution, user=user)
                solution.downvotes += 1
                message = 'Solution downvoted successfully'
            else:
                return {
                    'conflict': True,  
                    'error': 'Already downvoted',
                    'messages': [{'message': 'You have already downvoted this solution', 'tags': 'info'}]
                }
        
        solution.save()
        return {
            'success': True,
            'upvotes': solution.upvotes,
            'downvotes': solution.downvotes,
            'vote_state': 'upvoted' if SolutionUpvote.objects.filter(solution=solution, user=user).exists() 
                         else 'downvoted' if SolutionDownvote.objects.filter(solution=solution, user=user).exists() 
                         else 'none',
            'messages': [{'message': message, 'tags': 'success'}]
        }
    except Exception as e:
        return {
            'error': str(e),
            'messages': [{'message': f'Error processing vote: {str(e)}', 'tags': 'error'}]
        }

def accept_solution_service(user, solution_id):
    try:
        solution = get_object_or_404(Solution, id=solution_id)
        post = solution.post
        
        if user != post.author:
            return {
                'error': 'Only the post author can accept solutions',
                'messages': [{'message': 'Only the post author can accept solutions', 'tags': 'error'}]
            }
        
        if post.accepted_solution == solution:
            # Unaccept the solution
            previous_solution_id = solution.id
            post.accepted_solution = None
            post.solved = False
            post.save()
            return {
                'success': True,
                'message': 'Solution unmarked as accepted',
                'is_accepted': False,
                'previous_solution_id': previous_solution_id,
                'messages': [{'message': 'Solution unmarked as accepted', 'tags': 'success'}]
            }
        else:
            # Accept the new solution
            previous_solution_id = post.accepted_solution.id if post.accepted_solution else None
            post.accepted_solution = solution
            post.solved = True
            post.save()
            return {
                'success': True,
                'message': 'Solution marked as accepted',
                'is_accepted': True,
                'previous_solution_id': previous_solution_id,
                'messages': [{'message': 'Solution marked as accepted', 'tags': 'success'}]
            }
            
    except Exception as e:
        return {
            'error': str(e),
            'messages': [{'message': f'Error accepting solution: {str(e)}', 'tags': 'error'}]
        }

def save_solution_service(user, solution_id):
    try:
        solution = get_object_or_404(Solution, id=solution_id)
        
        if SavedSolution.objects.filter(solution=solution, user=user).exists():
            SavedSolution.objects.filter(solution=solution, user=user).delete()
            return {
                'success': True,
                'saved': False,
                'messages': [{'message': 'Solution removed from saved items', 'tags': 'success'}]
            }
        else:
            SavedSolution.objects.create(solution=solution, user=user)
            return {
                'success': True,
                'saved': True,
                'messages': [{'message': 'Solution saved successfully', 'tags': 'success'}]
            }
            
    except Exception as e:
        return {
            'error': str(e),
            'messages': [{'message': f'Error saving solution: {str(e)}', 'tags': 'error'}]
        }

def get_sorted_solutions_service(post_id, sort_by='votes'):
    try:
        post = get_object_or_404(Post, id=post_id)
        solutions = Solution.objects.filter(post=post)
        
        if sort_by == 'votes':
            # First get accepted solution if exists
            solutions = solutions.annotate(
                vote_score=F('upvotes') - F('downvotes')
            ).order_by('-vote_score')
        elif sort_by == 'recency':
            solutions = solutions.order_by('-created_at')
        
        # Always ensure accepted solution is first if it exists
        if post.accepted_solution:
            solutions = list(solutions)
            if post.accepted_solution in solutions:
                solutions.remove(post.accepted_solution)
                solutions.insert(0, post.accepted_solution)
        
        return {
            'success': True,
            'solutions': solutions
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'messages': [{'message': f'Error fetching solutions: {str(e)}', 'tags': 'error'}]
        }
