from django.shortcuts import get_object_or_404
from django.db.models import (
    Case,
    Count,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from forum.models import (
    Comment,
    Course,
    FollowedPost,
    Poll,
    PollOption,
    Post,
    PostLike,
    SavedSolution,
    Solution,
    SolutionDownvote,
    SolutionUpvote,
    UserCourseExperience,
    UserCourseHelp,
)
from forum.services.utils import detect_bad_words
from forum.services.notification_services import send_course_notifications_service
from forum.services.mention_service import update_mentions
from forum.services.comment_tree import attach_comment_trees
import logging

logger = logging.getLogger(__name__)


def _check_teacher_visibility(user, post):
    """
    Check if a teacher can view this post.
    Raises ValueError if teacher cannot view the post.
    """
    if user and user.is_authenticated and user.is_teacher and not post.allow_teacher:
        raise ValueError("You don't have permission to view this post.")
    return True


def _count_subquery(queryset, group_field):
    return queryset.order_by().values(group_field).annotate(
        total=Count('pk')
    ).values('total')


def get_post_detail_object(post_id, user):
    """Load the complete post-detail graph in a fixed number of queries."""
    like_count = _count_subquery(
        PostLike.objects.filter(post_id=OuterRef('pk')),
        'post_id',
    )
    solution_count = _count_subquery(
        Solution.objects.filter(post_id=OuterRef('pk')),
        'post_id',
    )
    comment_count = _count_subquery(
        Comment.objects.filter(solution__post_id=OuterRef('pk')),
        'solution__post_id',
    )
    followers_count = _count_subquery(
        FollowedPost.objects.filter(post_id=OuterRef('pk')),
        'post_id',
    )

    courses = Course.objects.annotate(
        detail_is_experienced=Exists(
            UserCourseExperience.objects.filter(
                user=user,
                course_id=OuterRef('pk'),
            )
        ),
        detail_needs_help=Exists(
            UserCourseHelp.objects.filter(
                user=user,
                course_id=OuterRef('pk'),
                active=True,
            )
        ),
    ).prefetch_related('blocks')

    post = get_object_or_404(
        Post.objects.select_related(
            'author',
            'author__userprofile',
        ).prefetch_related(
            Prefetch('courses', queryset=courses),
        ).annotate(
            detail_like_count=Coalesce(
                Subquery(like_count, output_field=IntegerField()),
                Value(0),
            ),
            detail_solution_count=Coalesce(
                Subquery(solution_count, output_field=IntegerField()),
                Value(0),
            ),
            detail_comment_count=Coalesce(
                Subquery(comment_count, output_field=IntegerField()),
                Value(0),
            ),
            detail_followers_count=Coalesce(
                Subquery(followers_count, output_field=IntegerField()),
                Value(0),
            ),
            detail_is_liked=Exists(
                PostLike.objects.filter(post_id=OuterRef('pk'), user=user)
            ),
            detail_is_following=Exists(
                FollowedPost.objects.filter(post_id=OuterRef('pk'), user=user)
            ),
            detail_has_solution_from_user=Exists(
                Solution.objects.filter(post_id=OuterRef('pk'), author=user)
            ),
        ),
        id=post_id,
    )

    # Avoid loading the nested graph when the caller will reject this post.
    if user.is_teacher and not post.allow_teacher:
        return post

    solutions = list(
        Solution.objects.filter(post=post).select_related(
            'author',
            'author__userprofile',
        ).annotate(
            vote_score=F('upvotes') - F('downvotes'),
            detail_is_saved=Exists(
                SavedSolution.objects.filter(
                    solution_id=OuterRef('pk'),
                    user=user,
                )
            ),
            detail_viewer_has_upvoted=Exists(
                SolutionUpvote.objects.filter(
                    solution_id=OuterRef('pk'),
                    user=user,
                )
            ),
            detail_viewer_has_downvoted=Exists(
                SolutionDownvote.objects.filter(
                    solution_id=OuterRef('pk'),
                    user=user,
                )
            ),
        ).order_by(
            Case(
                When(id=post.accepted_solution_id, then=0),
                default=1,
                output_field=IntegerField(),
            ),
            '-vote_score',
            '-created_at',
        )
    )
    solution_ids = [solution.id for solution in solutions]

    comments = list(
        Comment.objects.filter(solution_id__in=solution_ids).select_related(
            'author',
            'author__userprofile',
        ).order_by('created_at')
    )
    roots_by_solution = attach_comment_trees(comments, solution_ids)

    for solution in solutions:
        solution.detail_is_accepted = solution.id == post.accepted_solution_id
        solution.detail_root_comments = roots_by_solution[solution.id]

    post.detail_solutions = solutions
    return post


def create_post_service(user, data):
    try:
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
            return {'error': 'Content is required'}

        detect_bad_words(content)
        
        post = Post(
            author=user,
            title=data.get('title'),
            content=content,
            post_type='standard',
            is_anonymous=data.get("is_anonymous"),
            allow_teacher=data.get("allow_teacher", False),
        )
        post.save()

        update_mentions(post, content, old_content=None)

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

        post.save()

        # Update mentions if content was updated
        if 'content' in data:
            update_mentions(post, data['content'], old_content=old_content)

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
        
        # Check teacher visibility
        _check_teacher_visibility(user, post)
        
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
        
        # Check teacher visibility
        _check_teacher_visibility(user, post)
        
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
        
        # Check teacher visibility
        _check_teacher_visibility(user, post)
        
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
        
        # Check teacher visibility
        _check_teacher_visibility(user, post)
        
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
        
        # Check teacher visibility
        _check_teacher_visibility(request.user if request.user.is_authenticated else None, post)
        
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

def create_poll_service(user, data):
    """
    Service to create a poll with options
    """
    try:
        title = data.get('question')
        if not title:
            return {'error': 'Poll question is required'}

        content = data.get('content', {})
        if not content:
            content = {"blocks": [{"type": "paragraph", "data": {"text": f"{title}"}}]}

        # Validate answers
        answers = data.get('answers', [])
        if len(answers) < 2:
            return {'error': 'At least 2 answers are required for a poll'}

        # Create poll
        poll = Poll(
            author=user,
            title=title,
            content=content,
            post_type='poll',
            is_anonymous=data.get('is_anonymous', False),
            allow_teacher=data.get('allow_teacher', False),
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

        return {
            'id': poll.id,
            'url': poll.get_absolute_url(),
            'message': 'Poll created successfully'
        }
    except Exception as e:
        logger.error(f"Error creating poll: {str(e)}")
        return {'error': str(e)}
