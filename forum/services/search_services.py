from django.db.models import Value, F, Count, Q
from django.db.models.functions import Concat, Greatest
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from forum.models import Post, User
from forum.services.utils import process_post_preview, add_course_context, annotate_post_card_context
from forum.services.course_services import get_user_courses

def search_posts(user, query):
    search_query = SearchQuery(query)
    posts = Post.objects.annotate(
        rank=SearchRank(F('search_vector'), search_query) + TrigramSimilarity('title', query),
        solution_count=Count('solutions', distinct=True),
        comment_count=Count('solutions__comments', distinct=True),
        total_response_count=Count('solutions', distinct=True) + Count('solutions__comments', distinct=True)
    ).filter(rank__gte=0.3)
    
    if user.is_authenticated and user.is_teacher:
        posts = posts.filter(allow_teacher=True)
    
    posts = posts.order_by('-rank')

    posts = annotate_post_card_context(posts, user)
    return posts

def search_users(user, query):
    query = query.strip()

    qs = User.objects.annotate(
        trigram_first=TrigramSimilarity('first_name', query),
        trigram_last=TrigramSimilarity('last_name', query),
        trigram_full=TrigramSimilarity(
            Concat(F('first_name'), Value(' '), F('last_name')),
            query
        ),
        similarity=Greatest(
            F('trigram_first'),
            F('trigram_last'),
            F('trigram_full'),
        )
    ).filter(
        similarity__gte=0.1
    ).order_by('-similarity')

    return qs

