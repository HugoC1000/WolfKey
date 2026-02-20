from django.shortcuts import get_object_or_404
from django.db.models import F, Case, When, IntegerField
from forum.models import Post, Course, PostLike, FollowedPost
from forum.services.utils import detect_bad_words, selective_quote_replace
from forum.services.notification_services import send_course_notifications_service
import json
import logging

logger = logging.getLogger(__name__)

def get_post_detail_service(post_id, user=None):
    try:
        post = get_object_or_404(Post, id=post_id)
        solutions = post.solutions.annotate(
            vote_score=F('upvotes') - F('downvotes')
        ).order_by(
            Case(
                When(id=post.accepted_solution_id, then=0),
                default=1,
                output_field=IntegerField(),
            ),
            '-vote_score',
            '-created_at'
        )

        processed_solutions = []
        for solution in solutions:
            try:
                solution_content = solution.content
                if isinstance(solution_content, str):
                    solution_content = selective_quote_replace(solution_content)
                    solution_content = json.loads(solution_content)
                
                comments = solution.comments.select_related('author').order_by('created_at')
                processed_comments = [{
                    'id': comment.id,
                    'content': comment.content,
                    'author': comment.author.get_full_name(),
                    'created_at': comment.created_at.isoformat(),
                    'parent_id': comment.parent_id,
                    'depth': comment.get_depth(),
                } for comment in comments]

                processed_solutions.append({
                    'id': solution.id,
                    'content': solution_content,
                    'author': solution.author.get_full_name(),
                    'created_at': solution.created_at.isoformat(),
                    'upvotes': solution.upvotes,
                    'downvotes': solution.downvotes,
                    'comments': processed_comments,
                })
            except Exception as e:
                logger.error(f"Error processing solution {solution.id}: {e}")

        post = Post.objects.get(id=post_id)
        post.views += 1
        post.save()

        return {
            'id': post.id,
            'title': post.title,
            'solutions_object' : solutions,
            'content': post.content,
            'author': post.author.get_full_name(),
            'created_at': post.created_at.isoformat(),
            'solutions': processed_solutions,
            'courses': [{'id': c.id, 'name': c.name} for c in post.courses.all()],
            'like_count': post.like_count(),
            'is_liked': post.is_liked_by(user) if user else False,
        }
    except Exception as e:
        return {'error': str(e)}

def create_post_service(user, data):
    try:
        content = data.get('content')
        if not content:
            return {'error': 'Content is required'}

        detect_bad_words(content)
        
        post = Post(
            author=user,
            title=data.get('title'),
            content=content,
            is_anonymous=data.get("is_anonymous"),
            allow_teacher=data.get("allow_teacher", False),
        )
        post.save()

        course_ids = data.get('courses', [])
        if course_ids:
            courses = Course.objects.filter(id__in=course_ids)
            post.courses.set(courses)
            send_course_notifications_service(post, courses)

        return {
            'id': post.id,
            'url': post.get_absolute_url(),
            'message': 'Post created successfully'
        }
    except ValueError as e:
        return {'error': f"Content contains inappropriate language: {str(e)}"}
    except Exception as e:
        return {'error': str(e)}

def update_post_service(user, post_id, data):
    try:
        post = get_object_or_404(Post, id=post_id)
        
        if post.author != user:
            return {'error': 'Permission denied'}

        if 'content' in data:
            content = data['content']
            detect_bad_words(content)
            post.content = content

        if 'title' in data:
            post.title = data['title']

        if 'is_anonymous' in data:
            post.is_anonymous = data['is_anonymous']
        
        if 'allow_teacher' in data:
            post.allow_teacher = data['allow_teacher']

        if 'courses' in data:
            course_ids = data['courses']
            courses = Course.objects.filter(id__in=course_ids)
            post.courses.set(courses)

        post.save()
        return {'message': 'Post updated successfully'}
    except ValueError as e:
        return {'error': f"{str(e)}"}
    except Exception as e:
        return {'error': str(e)}

def delete_post_service(user, post_id):
    try:
        post = get_object_or_404(Post, id=post_id)
        
        if post.author != user:
            return {'error': 'Permission denied'}
            
        post.delete()
        return {'message': 'Post deleted successfully'}
    except Exception as e:
        return {'error': str(e)}

def like_post_service(user, post_id):
    """
    Service to like a post
    """
    try:
        post = get_object_or_404(Post, id=post_id)
        like, created = PostLike.objects.get_or_create(user=user, post=post)
        
        return {
            'success': True,
            'liked': True,
            'like_count': post.like_count(),
            'created': created
        }
    except Exception as e:
        logger.error(f"Error liking post {post_id}: {str(e)}")
        return {'error': str(e)}

def unlike_post_service(user, post_id):
    """
    Service to unlike a post
    """
    try:
        post = get_object_or_404(Post, id=post_id)
        deleted_count, _ = PostLike.objects.filter(user=user, post=post).delete()
        
        return {
            'success': True,
            'liked': False,
            'like_count': post.like_count(),
            'was_liked': deleted_count > 0
        }
    except Exception as e:
        logger.error(f"Error unliking post {post_id}: {str(e)}")
        return {'error': str(e)}

def follow_post_service(user, post_id):
    """
    Service to follow a post
    """
    try:
        post = get_object_or_404(Post, id=post_id)
        followed, created = FollowedPost.objects.get_or_create(user=user, post=post)
        
        return {
            'success': True,
            'followed': True,
            'followers_count': post.followers.count(),
            'created': created
        }
    except Exception as e:
        logger.error(f"Error following post {post_id}: {str(e)}")
        return {'error': str(e)}

def unfollow_post_service(user, post_id):
    """
    Service to unfollow a post
    """
    try:
        post = get_object_or_404(Post, id=post_id)
        deleted_count, _ = FollowedPost.objects.filter(user=user, post=post).delete()
        
        return {
            'success': True,
            'followed': False,
            'followers_count': post.followers.count(),
            'was_following': deleted_count > 0
        }
    except Exception as e:
        logger.error(f"Error unfollowing post {post_id}: {str(e)}")
        return {'error': str(e)}

def get_post_share_info_service(post_id, request):
    """
    Service to get post share information
    """
    try:
        post = get_object_or_404(Post, id=post_id)
        
        # Build absolute URL for the post
        post_url = request.build_absolute_uri(f'/post/{post_id}/')
        
        return {
            'success': True,
            'post_id': post.id,
            'post_title': post.title,
            'post_url': post_url,
            'author': post.author.get_full_name() if not post.is_anonymous else 'Anonymous',
            'created_at': post.created_at.isoformat(),
            'preview_text': post.preview_text[:250] if hasattr(post, 'preview_text') else (post.title[:250] if post.title else '')
        }
    except Exception as e:
        logger.error(f"Error getting share info for post {post_id}: {str(e)}")
        return {'error': str(e)}

def get_post_share_info_service(post_id, request):
    """
    Service to get post share information including URL
    """
    try:
        post = get_object_or_404(Post, id=post_id)
        
        # Build absolute URL for sharing
        if request:
            base_url = request.build_absolute_uri('/').rstrip('/')
            post_url = f"{base_url}/posts/{post_id}/"
        else:
            post_url = f"/posts/{post_id}/"
        
        return {
            'success': True,
            'post_id': post_id,
            'post_title': post.title,
            'post_url': post_url,
            'author': post.author.get_full_name() if not post.is_anonymous else 'Anonymous',
            'created_at': post.created_at.isoformat(),
            'preview_text': post.preview_text[:200] + '...' if len(post.preview_text) > 200 else post.preview_text
        }
    except Exception as e:
        logger.error(f"Error getting share info for post {post_id}: {str(e)}")
        return {'error': str(e)}
