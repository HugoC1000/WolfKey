from forum.models import Post, Solution, SolutionUpvote, SolutionDownvote
from forum.services.utils import detect_bad_words
from forum.services.notification_services import send_solution_notification_service
from forum.services.mention_service import update_mentions
from forum.services.post_services import _check_teacher_visibility, record_post_activity
from forum.services.results import service_error
from django.db.models import F
import json


def get_solution_for_author(user, solution_id):
    solution = Solution.objects.filter(id=solution_id, author=user).first()
    return {'solution': solution} if solution else service_error('Solution not found', 404)

def create_solution_service(user, post_id, data):
    try:
        post = Post.objects.get(id=post_id)

        # Check teacher visibility before content validation so each error has
        # an unambiguous status.
        try:
            _check_teacher_visibility(user, post)
        except ValueError as error:
            return service_error(error, 403)
        if Solution.objects.filter(post=post, author=user).exists():
            return service_error('You have already submitted a solution', 409)

        content = data.get('content')
        if not content:
            return service_error('Content is required')

        # Validate content
        if isinstance(content, dict) and 'blocks' in content:
            blocks = content.get('blocks', [])
            if (len(blocks) == 1 and 
                blocks[0].get('type') == 'paragraph' and 
                not blocks[0].get('data', {}).get('text', '').strip()) or len(blocks) == 0:
                return service_error('Solution cannot be empty')

        detect_bad_words(content)
        
        solution = Solution.objects.create(
            post=post,
            author=user,
            content=content
        )

        record_post_activity(post)
        
        # Update mentions in the solution content
        update_mentions(solution, content, old_content=None)
        
        if post.author != solution.author:
            send_solution_notification_service(solution)

        return {
            'id': solution.id,
            'message': 'Solution submitted successfully'
        }

    except ValueError as e:
        return service_error(e)
    except Post.DoesNotExist:
        return service_error('Post not found', 404)
    except Exception as e:
        return service_error(f'Error creating solution: {e}', 500)

def update_solution_service(user, solution_id, data):
    try:
        
        solution = Solution.objects.get(id=solution_id, author=user)
        old_content = solution.content
        content = data.get('content')
        
        if not content:
            return service_error('Content is required')

        detect_bad_words(content)
        solution.content = content
        solution.save()

        # Update mentions if content was updated
        update_mentions(solution, content, old_content=old_content)

        return {
            'message': 'Solution updated successfully',
            'id': solution.id
        }
    except ValueError as e:
        return service_error(e)
    except Solution.DoesNotExist:
        return service_error('Solution not found', 404)
    except Exception as e:
        return service_error(f'Error updating solution: {e}', 500)

def delete_solution_service(user, solution_id):
    try:
        solution = Solution.objects.get(id=solution_id, author=user)
        
        solution.delete()
        return {'message': 'Solution deleted successfully'}
    except Solution.DoesNotExist:
        return service_error('Solution not found', 404)
    except Exception as e:
        return service_error(e, 500)

def vote_solution_service(user, solution_id, vote_type):
    try:
        solution = Solution.objects.get(id=solution_id)
        
        # Check teacher visibility on the post
        _check_teacher_visibility(user, solution.post)
        
        if vote_type == 'upvote':
            if SolutionDownvote.objects.filter(solution=solution, user=user).exists():
                SolutionDownvote.objects.filter(solution=solution, user=user).delete()
                solution.downvotes -= 1
                SolutionUpvote.objects.create(solution=solution, user=user)
                solution.upvotes += 1
                message = 'Solution upvoted successfully'
            elif not SolutionUpvote.objects.filter(solution=solution, user=user).exists():
                SolutionUpvote.objects.create(solution=solution, user=user)
                solution.upvotes += 1
                message = 'Solution upvoted successfully'
            else:
                return service_error('Already upvoted', 409)
        else:  # downvote
            if SolutionUpvote.objects.filter(solution=solution, user=user).exists():
                SolutionUpvote.objects.filter(solution=solution, user=user).delete()
                solution.upvotes -= 1
                SolutionDownvote.objects.create(solution=solution, user=user)
                solution.downvotes += 1
                message = 'Solution downvoted successfully'
            elif not SolutionDownvote.objects.filter(solution=solution, user=user).exists():
                SolutionDownvote.objects.create(solution=solution, user=user)
                solution.downvotes += 1
                message = 'Solution downvoted successfully'
            else:
                return service_error('Already downvoted', 409)
        
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
    except Solution.DoesNotExist:
        return service_error('Solution not found', 404)
    except ValueError as e:
        return service_error(e, 403)
    except Exception as e:
        return service_error(e, 500)

def accept_solution_service(user, solution_id):
    try:
        solution = Solution.objects.get(id=solution_id)
        post = solution.post
        
        # Check teacher visibility
        _check_teacher_visibility(user, post)
        
        if user != post.author:
            return service_error('Only the post author can accept solutions', 403)
        
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
            
    except Solution.DoesNotExist:
        return service_error('Solution not found', 404)
    except ValueError as e:
        return service_error(e, 403)
    except Exception as e:
        return service_error(e, 500)

def get_sorted_solutions_service(post_id, sort_by='votes'):
    try:
        post = Post.objects.get(id=post_id)
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
        
    except Post.DoesNotExist:
        return service_error('Post not found', 404)
    except Exception as e:
        return service_error(e, 500)
