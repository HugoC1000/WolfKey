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
    mention_pattern = re.compile(r'@(\w+)')
    
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


def get_user_by_username(username: str) -> Optional[object]:
    """
    Check if a mentioned user exists.
    
    Args:
        username (str): Username to validate
    
    Returns:
        User | None: User object if found, None otherwise
    """
    try:
        # Try to find by username first
        user = User.objects.get(username=username)
        return user
    except User.DoesNotExist:
        return None


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
    # Prefer the structured parser name; wrappers keep older names available.
    text_mentions = parse_editorjs_text_mentions(content)

    valid_users = []
    seen_usernames = set()

    for mention in text_mentions:
        username = mention['username']

        # Skip duplicates
        if username in seen_usernames:
            continue

        user = get_user_by_username(username)
        if user:
            valid_users.append(user)
            seen_usernames.add(username)

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
    
    mention_pattern = re.compile(r'@(\w+)')
    
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
    from forum.services.notification_services import send_mention_notification_service
    
    # Determine content type and ID
    if isinstance(content_obj, Post):
        content_type = 'post'
    elif isinstance(content_obj, Solution):
        content_type = 'solution'
    elif isinstance(content_obj, Comment):
        content_type = 'comment'
    else:
        return
    
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


def fetch_mentions_for_content(content_obj) -> List[Dict]:
    """
    Get all mentions for a specific content object.
    
    Args:
        content_obj: Post, Solution, or Comment object
    
    Returns:
        list[dict]: List of mentions with {user_id, full_name, is_anonymous}
    """
    # Determine content type
    if isinstance(content_obj, Post):
        content_type = 'post'
    elif isinstance(content_obj, Solution):
        content_type = 'solution'
    elif isinstance(content_obj, Comment):
        content_type = 'comment'
    else:
        return []
    
    # Build the filter kwargs
    content_kwargs = {
        'content_type': content_type,
    }
    
    if content_type == 'post':
        content_kwargs['post'] = content_obj
    elif content_type == 'solution':
        content_kwargs['solution'] = content_obj
    elif content_type == 'comment':
        content_kwargs['comment'] = content_obj
    
    mentions = Mention.objects.filter(**content_kwargs).select_related('mentioned_user')
    
    return [
        {
            'user_id': mention.mentioned_user.id,
            'full_name': mention.mentioned_user.get_full_name() or mention.mentioned_user.username,
            'username': mention.mentioned_user.username,
            'is_anonymous': mention.is_anonymous
        }
        for mention in mentions
    ]


# Backwards-compatible wrappers (old names kept for callers). Prefer the new names above.
# Deprecated wrappers removed — import and call the new function names directly.
