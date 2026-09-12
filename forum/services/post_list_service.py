"""Build the viewer-specific data needed wherever posts are listed."""
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from django.db.models import Count
from django.utils.safestring import SafeString, mark_safe

from forum.models import FollowedPost, PostLike, Solution
from forum.services.course_services import course_category_class, course_category_color, get_user_courses
from forum.services.utils import process_post_preview, process_post_preview_html


@dataclass
class PostListItem:
    """A post plus the derived values required in a post collection."""

    post: Any
    preview_text: str
    preview_html: SafeString
    course_context: list[dict]
    is_liked: bool
    is_following: bool
    like_count: int
    followers_count: int
    solution_count: int
    comment_count: int
    response_count: int
    poll_data: dict | None


def prepare_posts(posts, viewer):
    """Return explicit list data for an already-filtered collection of posts."""
    if hasattr(posts, 'select_related'):
        posts = list(posts.select_related('author', 'author__userprofile').prefetch_related('courses'))
    else:
        posts = list(posts)
    if not posts:
        return []

    post_ids = [post.id for post in posts]
    experienced_courses, help_needed_courses = get_user_courses(viewer)
    experienced_ids = {course.id for course in experienced_courses}
    help_needed_ids = {course.id for course in help_needed_courses}

    liked_ids = set()
    followed_ids = set()
    if viewer.is_authenticated:
        liked_ids = set(viewer.liked_posts.filter(post_id__in=post_ids).values_list('post_id', flat=True))
        followed_ids = set(viewer.followed_posts.filter(post_id__in=post_ids).values_list('post_id', flat=True))

    like_counts = dict(
        PostLike.objects.filter(post_id__in=post_ids)
        .values_list('post_id')
        .annotate(count=Count('id'))
    )
    follower_counts = dict(
        FollowedPost.objects.filter(post_id__in=post_ids)
        .values_list('post_id')
        .annotate(count=Count('id'))
    )
    response_counts = {
        row['post_id']: (row['solutions'], row['comments'])
        for row in Solution.objects.filter(post_id__in=post_ids)
        .values('post_id')
        .annotate(solutions=Count('id', distinct=True), comments=Count('comments', distinct=True))
    }

    from forum.serializers.poll import serialize_poll_display_data

    prepared_posts = []
    for post in posts:
        solution_count, comment_count = response_counts.get(post.id, (0, 0))
        courses = [
            {
                'id': course.id,
                'name': course.name,
                'color': course_category_color(course.category),
                'category_class': course_category_class(course.category),
                'is_experienced': course.id in experienced_ids,
                'needs_help': course.id in help_needed_ids,
            }
            for course in post.courses.all()
        ]
        prepared_posts.append(PostListItem(
            post=post,
            preview_text=process_post_preview(post),
            preview_html=mark_safe(process_post_preview_html(post)),
            course_context=courses,
            is_liked=post.id in liked_ids,
            is_following=post.id in followed_ids,
            like_count=like_counts.get(post.id, 0),
            followers_count=follower_counts.get(post.id, 0),
            solution_count=solution_count,
            comment_count=comment_count,
            response_count=solution_count + comment_count,
            poll_data=serialize_poll_display_data(
                post, request=SimpleNamespace(user=viewer)
            ) if post.post_type == 'poll' else None,
        ))
    return prepared_posts
