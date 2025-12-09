from django import template
from django.template.defaultfilters import timesince
from django.utils import timezone
from datetime import timedelta


register = template.Library()

@register.filter(name='endswith')
def endswith(value, arg):
    return value.lower().endswith(arg)


@register.filter
def image_files(files):
    return [file for file in files if file.file.url.lower().endswith(('.jpg', '.jpeg', '.png'))]


@register.filter
def media_files(files):
    return [file for file in files if file.file.url.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.webm', '.ogg'))]

@register.filter
def exclude_media_files(files):
    return [file for file in files if not file.file.url.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.webm', '.ogg'))]

@register.filter(name='remove_upload')
def remove_upload(value):
    return value.replace('uploads/', '')

@register.filter
def vote_difference(solution):
    return solution.upvotes - solution.downvotes

@register.filter
def has_upvoted(solution, user):
    return solution.solutionupvote_set.filter(user=user).exists()

@register.filter
def has_downvoted(solution, user):
    return solution.solutiondownvote_set.filter(user=user).exists()


@register.filter
def is_saved_solution(solution, user):
    if not user.is_authenticated:
        return False
    return solution.saves.filter(user=user).exists()

@register.simple_tag
def increment(value):
    """Increments a counter by 1."""
    return value + 1

@register.filter
def smart_timesince(value, days=30):
    """
    Render *value* (a timezone‑aware ``datetime``) as a relative string
    when it is younger than *days*; otherwise fall back to an
    absolute date formatted as “Month DD, YYYY”.

    Usage in template:
        {% load post_extras %}
        {{ post.created_at|smart_timesince }}             # 30‑day default
        {{ post.created_at|smart_timesince:45 }}           # custom window
    """
    if not value:
        return ""
    threshold = timezone.now() - timedelta(days=int(days))
    if value >= threshold:
        return f"{timesince(value)}"
    return value.strftime("%B %d, %Y")
