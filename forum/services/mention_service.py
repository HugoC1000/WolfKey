import re
from typing import List, Dict, Optional
from django.contrib.auth import get_user_model
from forum.models import Mention, Post, Solution, Comment

User = get_user_model()


def parse_editorjs_text_mentions(content: dict) -> List[Dict]:
    """
    Extract @username mentions from EditorJS text blocks.
    
    Searches through all text blocks and finds patterns like @username.
    Returns list of dicts with: {username, block_idx, start_pos, length}
    
    Args:
        content (dict): EditorJS content with 'blocks' key
    
    Returns:
        list[dict]: List of mentions found
    """
    if not isinstance(content, dict) or 'blocks' not in content:
        return []
    
    mentions = []
    mention_pattern = re.compile(r'@([\w.-]+)')
    
    for block_idx, block in enumerate(content.get('blocks', [])):
        if not isinstance(block, dict):
            continue
        
        # Text mentions are in paragraph blocks
        if block.get('type') not in ('paragraph', 'heading'):
            continue
        
        data = block.get('data', {})
        text = data.get('text', '')
        
        if not text:
            continue
        
        # Find all @username patterns
        for match in mention_pattern.finditer(text):
            mentions.append({
                'username': match.group(1),
                'block_idx': block_idx,
                'start_pos': match.start(),
                'length': len(match.group(0))  # Length of "@username"
            })
    return mentions


def parse_editorjs_course_mentions(content: dict) -> List[Dict]:
    """
    Extract #course mentions from EditorJS text blocks.
    
    Searches through all text blocks and finds patterns like:
    - #course_id-name (new format with ID)
    - #coursename (old format for backwards compatibility)
    
    Returns list of dicts with: {course_id, course_name, block_idx, start_pos, length}
    
    Args:
        content (dict): EditorJS content with 'blocks' key
    
    Returns:
        list[dict]: List of course mentions found
    """
    if not isinstance(content, dict) or 'blocks' not in content:
        return []
    
    mentions = []
    # Match both new format #course_id-name and old format #name
    course_pattern = re.compile(r'#(course_(\d+)-[^#\s]+|[\w\s.-]+?)(?=\s|$|[^a-zA-Z0-9\s._-])')
    
    for block_idx, block in enumerate(content.get('blocks', [])):
        if not isinstance(block, dict):
            continue
        
        # Course mentions are in paragraph blocks
        if block.get('type') not in ('paragraph', 'heading'):
            continue
        
        data = block.get('data', {})
        text = data.get('text', '')
        
        if not text:
            continue
        
        # Find all #course mentions
        for match in course_pattern.finditer(text):
            course_identifier = match.group(1).strip()
            course_id = None
            course_name = course_identifier
            
            # Check if it's the new format: course_id-name
            id_match = re.match(r'^course_(\d+)-(.+)$', course_identifier)
            if id_match:
                course_id = int(id_match.group(1))
                course_name = id_match.group(2)
            
            mentions.append({
                'course_id': course_id,
                'course_name': course_name,
                'block_idx': block_idx,
                'start_pos': match.start(),
                'length': len(match.group(0))
            })
    
    return mentions


def parse_editorjs_mark_mentions(content: dict) -> List[Dict]:
    """
    Extract mentions that are already stored as EditorJS marks.
    
    Parses the 'marks' array in text blocks that have type: 'mention'.
    
    Args:
        content (dict): EditorJS content with 'blocks' key
    
    Returns:
        list[dict]: List of mentions with {user_id, username, block_idx}
    """
    if not isinstance(content, dict) or 'blocks' not in content:
        return []
    
    mentions = []
    
    for block_idx, block in enumerate(content.get('blocks', [])):
        if not isinstance(block, dict):
            continue
        
        data = block.get('data', {})
        marks = data.get('marks', [])
        
        # Look for mention marks
        for mark in marks:
            if mark.get('type') == 'mention':
                mentions.append({
                    'user_id': mark.get('user_id'),
                    'block_idx': block_idx,
                    'start': mark.get('start'),
                    'length': mark.get('length')
                })
    
    return mentions


def resolve_mentioned_users_from_content(content: dict) -> List[object]:
    """
    Extract valid User objects for all mentions in content.
    
    Looks for @username patterns in text blocks and returns User objects.
    Skips non-existent users and duplicates.
    
    Args:
        content (dict): EditorJS content
    
    Returns:
        list[User]: List of valid User objects who are mentioned
    """
    # Prefer structured mention marks when available, then fall back to text parsing.
    mark_mentions = parse_editorjs_mark_mentions(content)
    text_mentions = parse_editorjs_text_mentions(content)

    valid_users = []
    seen_user_ids = set()

    # First pass: resolve from mark user IDs.
    for mention in mark_mentions:
        user = User.objects.filter(id=mention.get('user_id')).first()
        if not user:
            continue
        if user.id in seen_user_ids:
            continue
        valid_users.append(user)
        seen_user_ids.add(user.id)

    # Second pass: fallback text parsing for legacy/plain @username mentions.
    for mention in text_mentions:
        username = mention['username']

        user = User.objects.filter(username__iexact=username).first()
        if user:
            if user.id in seen_user_ids:
                continue
            valid_users.append(user)
            seen_user_ids.add(user.id)

    return valid_users


def add_editorjs_mention_marks(content: dict, mentions: List[object]) -> Dict:
    """
    Add EditorJS mention marks to content based on extracted @username patterns.
    
    Finds @username patterns in text and adds corresponding marks.
    This enriches the content with position metadata for rendering.
    
    Args:
        content (dict): EditorJS content
        mentions (list[User]): List of User objects to mark
    
    Returns:
        dict: Modified content with mention marks added
    """
    if not isinstance(content, dict) or 'blocks' not in content:
        return content
    
    import copy
    content = copy.deepcopy(content)
    
    # Build a map of username -> user_id for quick lookups
    mention_map = {user.username: user.id for user in mentions}
    
    mention_pattern = re.compile(r'@([\w.-]+)')
    
    for block in content.get('blocks', []):
        if not isinstance(block, dict):
            continue
        
        if block.get('type') not in ('paragraph', 'heading'):
            continue
        
        data = block.get('data', {})
        text = data.get('text', '')
        
        if not text or not data.get('marks'):
            data['marks'] = []
        
        # Find all @username patterns and add marks
        for match in mention_pattern.finditer(text):
            username = match.group(1)
            if username in mention_map:
                mark = {
                    'type': 'mention',
                    'start': match.start(),
                    'length': len(match.group(0)),
                    'user_id': mention_map[username]
                }
                # Avoid duplicate marks
                if mark not in data['marks']:
                    data['marks'].append(mark)
    
    return content


def resolve_content_object(content_id: int, content_type: str):
    """
    Get the content object (Post, Solution, or Comment) from content_type and ID.
    
    Args:
        content_id (int): ID of the content object
        content_type (str): 'post', 'solution', or 'comment'
    
    Returns:
        tuple: (content_object, content_type) or (None, None) if not found
    """
    try:
        if content_type == 'post':
            return Post.objects.get(id=content_id), content_type
        elif content_type == 'solution':
            return Solution.objects.get(id=content_id), content_type
        elif content_type == 'comment':
            return Comment.objects.get(id=content_id), content_type
    except (Post.DoesNotExist, Solution.DoesNotExist, Comment.DoesNotExist):
        return None, None
    
    return None, None


def update_mentions(content_obj, new_content: dict, old_content: Optional[dict] = None):
    """
    Update Mention records to match mentions in content.
    
    Compares mentions in new_content with old_content (if provided).
    Creates Mention records for new mentions, deletes for removed mentions.
    Automatically skips self-mentions and sends notifications.
    
    Args:
        content_obj: Post, Solution, or Comment object
        new_content (dict): New EditorJS content with mentions
        old_content (dict | None): Previous EditorJS content (for edits)
    """
    from forum.services.notification_services import (
        send_mention_notification_service,
        send_channel_notification_service,
        send_everyone_notification_service
    )
    from forum.models import Course

    # Determine content type and ID
    if isinstance(content_obj, Post):
        content_type = 'post'
    elif isinstance(content_obj, Solution):
        content_type = 'solution'
    elif isinstance(content_obj, Comment):
        content_type = 'comment'
    else:
        return
    
    # ===== HANDLE USER MENTIONS =====
    # Get mentioned users from new content
    new_mentions = resolve_mentioned_users_from_content(new_content)
    new_mention_ids = {user.id for user in new_mentions}
    
    # Get mentioned users from old content (if this is an edit)
    old_mentions = []
    if old_content:
        old_mentions = resolve_mentioned_users_from_content(old_content)
    old_mention_ids = {user.id for user in old_mentions}
    
    # Build the kwargs dict for filtering/creating Mention records
    content_kwargs = {content_type: content_obj}
    
    # Find users to remove mentions for (were in old, not in new)
    to_remove_ids = old_mention_ids - new_mention_ids
    if to_remove_ids:
        Mention.objects.filter(
            author=content_obj.author,
            mentioned_user_id__in=to_remove_ids,
            content_type=content_type,
            **content_kwargs
        ).delete()
    
    # Find users to add mentions for (in new, not in old)
    to_add_ids = new_mention_ids - old_mention_ids
    for user in new_mentions:
        if user.id not in to_add_ids:
            continue
        
        # Skip self-mentions
        if user.id == content_obj.author.id:
            continue
        
        # Create or get the Mention record
        # Do not include `is_anonymous` in the lookup keys — treat it as an attribute
        # so that the unique constraint (author, mentioned_user, content_type, content_id)
        # is the single source of truth for deduplication. Set `is_anonymous` via defaults.
        mention, created = Mention.objects.get_or_create(
            author=content_obj.author,
            mentioned_user=user,
            content_type=content_type,
            **content_kwargs,
            defaults={'is_anonymous': getattr(content_obj, 'is_anonymous', False)}
        )
        
        # Send notification only for newly created mentions
        if created:
            send_mention_notification_service(
                mentioned_user=user,
                mention_author=content_obj.author,
                content_object=content_obj,
                is_anonymous=getattr(content_obj, 'is_anonymous', False)
            )
    
    # ===== HANDLE CHANNEL (COURSE) MENTIONS =====
    new_course_mentions = parse_editorjs_course_mentions(new_content)
    old_course_mentions = []
    if old_content:
        old_course_mentions = parse_editorjs_course_mentions(old_content)
    
    # Extract course objects from new mentions
    new_mentioned_courses = []
    new_course_ids = set()
    for mention in new_course_mentions:
        try:
            if mention.get('course_id'):
                # New format with course ID
                course = Course.objects.get(id=mention['course_id'])
            else:
                # Old format with course name - search by name
                course = Course.objects.get(name__iexact=mention['course_name'])
            
            if course.id not in new_course_ids:
                new_mentioned_courses.append(course)
                new_course_ids.add(course.id)
        except Course.DoesNotExist:
            pass
    
    # Extract course objects from old mentions (for comparison)
    old_course_ids = set()
    if old_content:
        for mention in old_course_mentions:
            try:
                if mention.get('course_id'):
                    course = Course.objects.get(id=mention['course_id'])
                else:
                    course = Course.objects.get(name__iexact=mention['course_name'])
                old_course_ids.add(course.id)
            except Course.DoesNotExist:
                pass
    # Send channel notifications only for newly mentioned courses
    newly_mentioned_course_ids = new_course_ids - old_course_ids
    if newly_mentioned_course_ids:
        newly_mentioned_courses = [c for c in new_mentioned_courses if c.id in newly_mentioned_course_ids]
        if newly_mentioned_courses:
            send_channel_notification_service(
                content_object=content_obj,
                mention_author=content_obj.author,
                courses=newly_mentioned_courses
            )
    
    # ===== HANDLE EVERYONE MENTIONS =====
    # Check if @everyone is mentioned in new content
    new_everyone_mentioned = '@everyone' in str(new_content)
    old_everyone_mentioned = False
    if old_content:
        old_everyone_mentioned = '@everyone' in str(old_content)
    
    # Send everyone notification only if newly mentioned (not in old_content)
    if new_everyone_mentioned and not old_everyone_mentioned:
        # Only send if user is admin/staff
        if content_obj.author and (content_obj.author.is_staff or content_obj.author.is_superuser):
            send_everyone_notification_service(
                content_object=content_obj,
                mention_author=content_obj.author
            )


def search_mentions(user, query: str, limit: int = 5, trigger: str = '') -> Dict:
    """
    Search for mentions across users, courses, and "everyone" (admin-only).
    
    Args:
        user: The requesting user object
        query (str): Search query string
        limit (int): Maximum results per category
        trigger (str): '@' for users/everyone, '#' for courses, '' to search all
    
    Returns:
        dict with keys: 'users', 'courses', 'everyone'
    """
    from forum.services.search_services import search_users
    from forum.services.course_services import search_courses
    
    results = {
        'users': [],
        'courses': [],
        'everyone': []
    }
    
    query = query.strip()
    if not query:
        return results
    
    # Search for users (when trigger is '@' or not specified)
    if trigger in ('@', ''):
        try:
            searched_users = search_users(user, query)[:limit]
            results['users'] = [
                {
                    'id': u.id,
                    'username': u.username,
                    'first_name': u.first_name,
                    'last_name': u.last_name,
                    'full_name': u.get_full_name() or u.username,
                    'profile_picture_url': u.userprofile.profile_picture.url if (hasattr(u, 'userprofile') and u.userprofile and u.userprofile.profile_picture) else None,
                    'type': 'user'
                }
                for u in searched_users
            ]
        except Exception as e:
            pass
    
    # Search for courses (when trigger is '#' or not specified)
    if trigger in ('#', ''):
        try:
            courses = search_courses(query, limit)
            
            results['courses'] = [
                {
                    'id': c.id,
                    'name': c.name,
                    'category': getattr(c, 'category', 'Course'),
                    'type': 'course'
                }
                for c in courses
            ]
        except Exception as e:
            pass
    
    # Add "everyone" option if user is admin (when trigger is '@' or not specified)
    if trigger in ('@', ''):
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            results['everyone'] = [
                {
                    'id': None,
                    'name': 'everyone',
                    'type': 'everyone'
                }
            ]
    
    return results


# Backwards-compatible wrappers (old names kept for callers). Prefer the new names above.
# Deprecated wrappers removed — import and call the new function names directly.
