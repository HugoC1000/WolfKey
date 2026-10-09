from django.utils import timezone
from django.db.models import F
from forum.models import Post, Course, PostLike, FollowedPost, Poll, PollOption
from forum.services.utils import detect_bad_words
from forum.services.notification_services import send_course_notifications_service, send_community_post_notifications_service
from forum.services.mention_service import update_mentions
from forum.services.results import service_error
import logging

logger = logging.getLogger(__name__)


def record_post_activity(post):
    """Move a post to the top of activity-based feeds after a new response."""
    activity_time = timezone.now()
    Post.objects.filter(id=post.id).update(last_activity_at=activity_time)
    post.last_activity_at = activity_time


def _check_teacher_visibility(user, post):
    """
    Check if a teacher can view this post.
    Raises ValueError if teacher cannot view the post.
    """
    if user and user.is_authenticated and user.is_teacher and not post.allow_teacher:
        raise ValueError("You don't have permission to view this post.")
    return True


def get_post_detail_service(user, post_id):
    """Load a visible post and count the page visit in one place."""
    post = Post.objects.filter(id=post_id).first()
    if post is None:
        return service_error('Post not found', 404)
    try:
        _check_teacher_visibility(user, post)
    except ValueError as error:
        return service_error(error, 404)
    Post.objects.filter(id=post_id).update(views=F('views') + 1)
    post.views += 1
    return {'post': post}


def get_post_for_author(user, post_id):
    post = Post.objects.filter(id=post_id).first()
    if post is None:
        return service_error('Post not found', 404)
    if post.author_id != user.id:
        return service_error('Permission denied', 403)
    return {'post': post}

def create_post_service(user, data):
    try:
        if not user.is_active:
            return service_error('This account is inactive and cannot create posts.', 403)
        # Check if this is a poll
        poll_data = data.get('poll_data')
        if poll_data and isinstance(poll_data, dict) and poll_data.get('isPoll'):
            # Create as poll
            poll_data['title'] = data.get('title')
            poll_data['content'] = data.get('content')
            poll_data['is_anonymous'] = data.get('is_anonymous', False)
            poll_data['allow_teacher'] = data.get('allow_teacher', False)
            poll_data['courses'] = data.get('courses', [])
            return create_poll_service(user, poll_data)
        
        # Regular post creation
        content = data.get('content')
        if not content:
            return service_error('Content is required')

        detect_bad_words(content)
        
        is_community_post = user.is_community_account
        post = Post(
            author=user,
            title=data.get('title'),
            content=content,
            post_type='standard',
            scope='community' if is_community_post else 'school',
            is_anonymous=False if is_community_post else data.get("is_anonymous"),
            allow_teacher=True if is_community_post else data.get("allow_teacher", False),
        )
        post.save()

        update_mentions(post, content, old_content=None)

        course_ids = data.get('courses', [])
        if course_ids:
            courses = Course.objects.filter(id__in=course_ids)
            post.courses.set(courses)
            send_course_notifications_service(post, courses)

        if is_community_post:
            send_community_post_notifications_service(post)

        return {
            'id': post.id,
            'url': post.get_absolute_url(),
            'message': 'Post created successfully'
        }
    except ValueError as e:
        return service_error(f"Content contains inappropriate language: {e}")
    except Exception as e:
        logger.exception('Error creating post')
        return service_error(e, 500)

def update_post_service(user, post_id, data):
    try:
        post = Post.objects.get(id=post_id)
        
        if post.author != user:
            return service_error('Permission denied', 403)

        # Store old content for mention comparison
        old_content = post.content if 'content' in data else None

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

        # Community posts keep the same invariants on edits as on creation,
        # regardless of which web or API client submitted the update.
        if user.is_community_account:
            post.scope = 'community'
            post.is_anonymous = False
            post.allow_teacher = True
            post.courses.clear()

        post.save()

        # Update mentions if content was updated
        if 'content' in data:
            update_mentions(post, data['content'], old_content=old_content)

        return {'message': 'Post updated successfully'}
    except ValueError as e:
        return service_error(e)
    except Post.DoesNotExist:
        return service_error('Post not found', 404)
    except Exception as e:
        logger.exception('Error updating post')
        return service_error(e, 500)

def delete_post_service(user, post_id):
    try:
        post = Post.objects.get(id=post_id)
        
        if post.author != user:
            return service_error('Permission denied', 403)
            
        post.delete()
        return {'message': 'Post deleted successfully'}
    except Post.DoesNotExist:
        return service_error('Post not found', 404)
    except Exception as e:
        logger.exception('Error deleting post')
        return service_error(e, 500)


def toggle_community_post_pin_service(user, post_id):
    """Pin only the author's community post; Home ordering never reads this flag."""
    post = Post.objects.filter(id=post_id).first()
    if post is None:
        return service_error('Post not found', 404)
    if post.author != user or not user.is_community_account or post.scope != 'community':
        return service_error('Only the owning community account can pin this post.', 403)
    post.is_pinned_in_community = not post.is_pinned_in_community
    post.save(update_fields=['is_pinned_in_community'])
    return {'pinned': post.is_pinned_in_community}

def like_post_service(user, post_id):
    """
    Service to like a post
    """
    try:
        post = Post.objects.get(id=post_id)
        
        # Check teacher visibility
        _check_teacher_visibility(user, post)
        
        like, created = PostLike.objects.get_or_create(user=user, post=post)
        
        return {
            'success': True,
            'liked': True,
            'like_count': post.like_count(),
            'created': created
        }
    except Post.DoesNotExist:
        return service_error('Post not found', 404)
    except ValueError as e:
        return service_error(e, 403)
    except Exception as e:
        logger.error(f"Error liking post {post_id}: {str(e)}")
        return service_error(e, 500)

def unlike_post_service(user, post_id):
    """
    Service to unlike a post
    """
    try:
        post = Post.objects.get(id=post_id)
        
        # Check teacher visibility
        _check_teacher_visibility(user, post)
        
        deleted_count, _ = PostLike.objects.filter(user=user, post=post).delete()
        
        return {
            'success': True,
            'liked': False,
            'like_count': post.like_count(),
            'was_liked': deleted_count > 0
        }
    except Post.DoesNotExist:
        return service_error('Post not found', 404)
    except ValueError as e:
        return service_error(e, 403)
    except Exception as e:
        logger.error(f"Error unliking post {post_id}: {str(e)}")
        return service_error(e, 500)

def follow_post_service(user, post_id):
    """
    Service to follow a post
    """
    try:
        post = Post.objects.get(id=post_id)
        
        # Check teacher visibility
        _check_teacher_visibility(user, post)
        
        followed, created = FollowedPost.objects.get_or_create(user=user, post=post)
        
        return {
            'success': True,
            'followed': True,
            'followers_count': post.followers.count(),
            'created': created
        }
    except Post.DoesNotExist:
        return service_error('Post not found', 404)
    except ValueError as e:
        return service_error(e, 403)
    except Exception as e:
        logger.error(f"Error following post {post_id}: {str(e)}")
        return service_error(e, 500)

def unfollow_post_service(user, post_id):
    """
    Service to unfollow a post
    """
    try:
        post = Post.objects.get(id=post_id)
        
        # Check teacher visibility
        _check_teacher_visibility(user, post)
        
        deleted_count, _ = FollowedPost.objects.filter(user=user, post=post).delete()
        
        return {
            'success': True,
            'followed': False,
            'followers_count': post.followers.count(),
            'was_following': deleted_count > 0
        }
    except Post.DoesNotExist:
        return service_error('Post not found', 404)
    except ValueError as e:
        return service_error(e, 403)
    except Exception as e:
        logger.error(f"Error unfollowing post {post_id}: {str(e)}")
        return service_error(e, 500)

def get_post_share_info_service(user, post_id):
    """
    Service to get post share information, enforcing normal post visibility.
    """
    try:
        post = Post.objects.get(id=post_id)

        # Check teacher visibility
        _check_teacher_visibility(user, post)

        relative_url = post.get_absolute_url()
        preview_text = getattr(post, 'preview_text', '') or post.title or ''

        return {
            'success': True,
            'post_id': post.id,
            'post_title': post.title,
            'post_url': relative_url,
            'author': post.author.get_full_name() if not post.is_anonymous else 'Anonymous',
            'created_at': post.created_at.isoformat(),
            'preview_text': preview_text[:250],
        }
    except Post.DoesNotExist:
        return service_error('Post not found', 404)
    except ValueError as e:
        return service_error(e, 403)
    except Exception as e:
        logger.error(f"Error getting share info for post {post_id}: {str(e)}")
        return service_error(e, 500)

def create_poll_service(user, data):
    """
    Service to create a poll with options
    """
    try:
        title = data.get('question')
        if not title:
            return service_error('Poll question is required')

        content = data.get('content', {})
        if not content:
            content = {"blocks": [{"type": "paragraph", "data": {"text": f"{title}"}}]}

        # Validate answers
        answers = data.get('answers', [])
        if len(answers) < 2:
            return service_error('At least 2 answers are required for a poll')

        # Create poll
        is_community_post = user.is_community_account
        poll = Poll(
            author=user,
            title=title,
            content=content,
            post_type='poll',
            scope='community' if is_community_post else 'school',
            is_anonymous=False if is_community_post else data.get('is_anonymous', False),
            allow_teacher=True if is_community_post else data.get('allow_teacher', False),
            allow_multiple_choice=data.get('allowMultiple', False),
            is_public_voting=data.get('isPublicVoting', True)
        )
        poll.save()

        # Create poll options
        for answer_text in answers:
            if answer_text.strip():
                PollOption.objects.create(poll=poll, text=answer_text.strip())

        # Add courses
        course_ids = data.get('courses', [])
        if course_ids:
            courses = Course.objects.filter(id__in=course_ids)
            poll.courses.set(courses)
            send_course_notifications_service(poll, courses)

        if is_community_post:
            send_community_post_notifications_service(poll)

        return {
            'id': poll.id,
            'url': poll.get_absolute_url(),
            'message': 'Poll created successfully'
        }
    except Exception as e:
        logger.error(f"Error creating poll: {str(e)}")
        return service_error(e, 500)
