"""Create and retrieve the feed post shown to clients using the legacy API."""

from forum.models import StandardPost, User

LEGACY_APP_UPDATE_TITLE = 'Update the app in the App Store — Posts are no longer available in this version'


def get_legacy_app_update_post():
    """Return the single admin-authored update post, creating it when possible."""
    admin = User.objects.filter(is_superuser=True).order_by('id').first()
    if admin is None:
        return None

    post = StandardPost.objects.filter(
        author=admin,
        content__contains={'system_notice': 'legacy_app_update'},
    ).order_by('id').first()
    if post is not None:
        if post.title != LEGACY_APP_UPDATE_TITLE:
            post.title = LEGACY_APP_UPDATE_TITLE
            post.save(update_fields=['title'])
        return post

    return StandardPost.objects.create(
        title=LEGACY_APP_UPDATE_TITLE,
        author=admin,
        content={
            'time': 0,
            'blocks': [],
            'version': '2.29.1',
            'system_notice': 'legacy_app_update',
        },
        content_markdown='',
        post_type='standard',
        scope='school',
        allow_teacher=True,
    )


def without_legacy_app_update_post(posts):
    """Keep the update notice out of regular web and current-app collections."""
    return posts.exclude(content__contains={'system_notice': 'legacy_app_update'})
