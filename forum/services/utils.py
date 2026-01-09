import re
import os
import uuid
from django.utils.html import strip_tags
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from forum.services.course_services import get_user_courses
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse

ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/heic']
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.heic']

def process_post_preview(post):
    """
    Generate a preview text for a post by extracting and cleaning paragraph blocks from Editor.js content.

    Args:
        post: Post object with a content attribute (dict or str).

    Returns:
        str: Concatenated and cleaned preview text.
    """
    if isinstance(post.content, dict) and 'blocks' in post.content:
        paragraphs = []
        for block in post.content['blocks']:
            if block.get('type') == 'paragraph':
                text = block.get('data', {}).get('text', '')
                text = re.sub(r'<br\s*/?>', ' ', text)
                text = re.sub(r'<i\s*/?>', ' ', text)
                text = re.sub(r'<em\s*/?>', ' ', text)
                text = text.replace('&nbsp;', ' ') 
                text = strip_tags(text)
                text = ' '.join(text.split())
                if text:
                    paragraphs.append(text)
        return ' '.join(paragraphs)
    else:
        text = str(post.content)
        text = re.sub(r'<br\s*/?>', ' ', text)
        text = strip_tags(text)
        return ' '.join(text.split())
    
def annotate_post_card_context(posts, user):
    from forum.models import FollowedPost
    
    experienced_courses, help_needed_courses = get_user_courses(user)
    
    post_ids = [post.id for post in posts]
    
    liked_post_ids = set()
    followed_post_ids = set()
    
    if user.is_authenticated:
        liked_post_ids = set(
            user.liked_posts.filter(post_id__in=post_ids).values_list('post_id', flat=True)
        )
        
        followed_post_ids = set(
            user.followed_posts.filter(post_id__in=post_ids).values_list('post_id', flat=True)
        )
    
    for post in posts:
        post.preview_text = process_post_preview(post)
        add_course_context(post, experienced_courses, help_needed_courses)
        
        post.is_liked_by_user = post.id in liked_post_ids
        post.is_following = post.id in followed_post_ids
    
    return posts


def add_course_context(post, experienced_courses=None, help_needed_courses=None):
    """
    Add course context information to a post object.

    Args:
        post: Post object with a courses relation.
        experienced_courses: Optional list of Course objects the user has experience with.
        help_needed_courses: Optional list of Course objects the user needs help with.

    Returns:
        post: The same post object with a 'course_context' attribute added.
    """
    post.course_context = []
    for course in post.courses.all():
        post.course_context.append({
            'name': course.name,
            'is_experienced': course in (experienced_courses or []),
            'needs_help': course in (help_needed_courses or [])
        })
    return post

@csrf_exempt
def upload_image(request):
    """
    Handle image uploads for Editor.js.

    - Ensures only allowed image types are accepted.
    - Converts all images to JPEG format.
    - Generates a unique filename for each upload.
    - Saves the image to the default Django storage.
    - Enforces a maximum file size of 500 MB.

    Args:
        request: Django HttpRequest object with an uploaded file in 'image'.

    Returns:
        JsonResponse: Success with image URL or error message.
    """
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  #10 MB

    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES['image']
        ext = os.path.splitext(image_file.name)[1].lower()
        mime_type = image_file.content_type

        # Check file size
        if image_file.size > MAX_IMAGE_SIZE:
            return JsonResponse({'error': 'Image file too large (max 10 MB).'}, status=400)

        # 1. Check allowed types
        if mime_type not in ALLOWED_IMAGE_TYPES or ext not in ALLOWED_EXTENSIONS:
            return JsonResponse({'error': 'Unsupported file type.'}, status=400)

        # 2. Open and convert to JPEG
        try:
            img = Image.open(image_file)
            rgb_img = img.convert('RGB')  # Convert to RGB for JPEG

            # 3. Generate unique filename
            unique_name = f"{uuid.uuid4().hex}.jpg"
            upload_path = os.path.join('uploads', unique_name)

            # 4. Save to BytesIO as JPEG
            buffer = BytesIO()
            rgb_img.save(buffer, format='JPEG', quality=90)
            buffer.seek(0)

            # 5. Save to storage
            saved_path = default_storage.save(upload_path, ContentFile(buffer.read()))
            image_url = default_storage.url(saved_path)

            return JsonResponse({'success': 1, 'file': {'url': image_url}})
        except Exception as e:
            return JsonResponse({'error': f'Image processing failed: {str(e)}'}, status=400)
    else:
        return JsonResponse({'error': 'No image uploaded'}, status=400)
    
def selective_quote_replace(content):
    """
    Replace quotes in content while preserving inlineMath quotes.

    Args:
        content (str): The content string to process.

    Returns:
        str: The processed content string with quotes replaced.
    """
    # First, preserve inlineMath quotes
    content = re.sub(r'data-tex="(.*?)"', r'data-tex=__INLINEMATH__\1__INLINEMATH__', content)
    
    # Do the regular quote replacements
    content = (content
        .replace('"', '\\"')  
        .replace("'", '"')        # Replace single quotes with double quotes
        .replace('data-tex="', 'data-tex=\\"')
        .replace('" style=', '\\" style=')
        .replace('style="', 'style=\\"')
        .replace('class="', 'class=\\"')
        .replace('" class=', '\\" class=')
        .replace('id="', 'id=\\"')
        .replace('" id=', '\\" id=')
        .replace(';">', ';\\">')
        .replace('" >', '\\">')
        .replace('"/>', '\\"/>')
        .replace('True', 'true')     
        .replace('False', 'false')
        .replace('None', 'null')
        .replace('\n', '\\n')
        .replace('\r', '\\r')
        .replace('\t', '\\t')
        .strip())

    # Restore inlineMath quotes
    content = content.replace("__INLINEMATH__", "'inline-math'")

    return content

def process_messages_to_json(request):
    """
    Convert Django messages to a JSON-serializable list.

    Args:
        request: Django HttpRequest object.

    Returns:
        list: List of dicts with 'message' and 'tags' keys.
    """
    messages_data = [
        {
            'message': message.message,
            'tags': message.tags
        }
        for message in messages.get_messages(request)
    ]

    return messages_data

leet_mapping = str.maketrans({
    '4': 'a', '@': 'a',
    '8': 'b',
    '(': 'c', '{': 'c', '[': 'c', '<': 'c',
    '3': 'e',
    '6': 'g', '9': 'g',
    '1': 'i', '!': 'i', '|': 'i',
    '0': 'o',
    '5': 's', '$': 's',
    '7': 't', '+': 't',
    '2': 'z'
})

def normalize_text(text):
    """
    Normalize text by converting leetspeak, removing special characters, and reducing repeated letters.

    Args:
        text (str): The input text.

    Returns:
        str: Normalized, lowercase text.
    """
    if not text:
        return ""
    
    text = text.translate(leet_mapping)  # Convert leetspeak
    text = re.sub(r'[^a-zA-Z\s]', '', text)  # Remove non-alphabetic characters, keep spaces
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize spaces
    text = re.sub(r'(.)\1{2,}', r'\1', text)  # Reduce repeated letters (e.g., "loooool" -> "lol")
    
    return text.lower()

bad_word_list = ['fuck', 'bitch', 'shit', 'ass', 'dick', 'cunt', 'cock', 'pussy']
bad_word_pattern = re.compile(r'\b(' + '|'.join(map(re.escape, bad_word_list)) + r')\b', re.IGNORECASE)

def detect_bad_words(content):
    """
    Detects bad words in plain text or structured Editor.js content.
    Raises ValueError if bad words are found, specifying the location.
    """
    if isinstance(content, str):
        normalized_text = normalize_text(content)
        if bad_word_pattern.search(normalized_text):
            raise ValueError("Bad word detected in text.")
    
    elif isinstance(content, dict) and 'blocks' in content:
        for block in content['blocks']:
            block_type = block.get("type", "unknown")
            data = block.get("data", {})
            
            text = data.get("text", "")
            items = data.get("items", [])
            
            if text:
                normalized_text = normalize_text(text)
                if bad_word_pattern.search(normalized_text):
                    raise ValueError(f"Bad word detected in block of type '{block_type}'.")
            
            for item in items:
                item_text = normalize_text(item.get("content"))
                if bad_word_pattern.search(item_text):
                    raise ValueError(f"Bad word detected in list item in block of type '{block_type}'.")
    else:
        raise ValueError("Unsupported content format for bad word detection.")

def extract_files_from_editorjs_content(content):
    """
    Extract file URLs from EditorJS content blocks.
    
    Args:
        content: EditorJS content (dict with 'blocks' key or similar structure)
        
    Returns:
        list: List of file URLs found in the content
    """
    file_urls = []
    
    if not isinstance(content, dict):
        return file_urls
    
    blocks = content.get('blocks', [])
    if not isinstance(blocks, list):
        return file_urls
    
    for block in blocks:
        if not isinstance(block, dict):
            continue
            
        block_type = block.get('type', '')
        block_data = block.get('data', {})
        
        if block_type == 'image':
            # Image data can be in 'file' or 'url' field
            image_url = block_data.get('file', {}).get('url') or block_data.get('url')
            if image_url:
                file_urls.append(image_url)
    
    return file_urls

def delete_files_from_urls(file_urls):
    """
    Delete files from the filesystem given their URLs.
    
    Args:
        file_urls: List of file URLs to delete
    """
    from urllib.parse import urlparse
    
    for url in file_urls:
        if not url:
            continue
            
        try:
            parsed_url = urlparse(url)
            file_path = parsed_url.path
            
            if file_path.startswith('/'):
                file_path = file_path[1:]
            
            if file_path.startswith('media/'):
                file_path = file_path[6:]
            
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
                print(f"Deleted file: {file_path}")
            else:
                print(f"File not found: {file_path}")
                
        except Exception as e:
            print(f"Error deleting file {url}: {str(e)}")

def upload_screenshot_to_storage(local_path, filename=None):
    """
    Upload a screenshot file to configured Django storage for debugging purposes.
    
    Args:
        local_path (str): Local file path of the screenshot
        filename (str): Optional custom filename, defaults to basename of local_path
        
    Returns:
        str: Storage URL of the uploaded screenshot, or None if upload failed
    """
    try:
        if not os.path.exists(local_path):
            print(f"Screenshot file not found: {local_path}")
            return None
            
        # Generate storage path
        if not filename:
            filename = os.path.basename(local_path)
        storage_path = f"debug/screenshots/{filename}"
        
        # Read the file content
        with open(local_path, 'rb') as f:
            file_content = f.read()
        
        # Save to Django's default storage
        stored_path = default_storage.save(storage_path, ContentFile(file_content))
        
        # Generate public URL
        storage_url = default_storage.url(stored_path)
        print(f"Screenshot uploaded to storage: {storage_url}")
        
        # Clean up local file
        try:
            os.remove(local_path)
            print(f"Cleaned up local screenshot: {local_path}")
        except Exception as e:
            print(f"Warning: Could not remove local file {local_path}: {e}")
            
        return storage_url
        
    except Exception as e:
        print(f"Error uploading screenshot to storage: {e}")
        return None

def extract_and_delete_files_from_content(content):
    """
    Extract and delete all files referenced in EditorJS content.
    
    Args:
        content: EditorJS content (dict with 'blocks' key)
    """
    file_urls = extract_files_from_editorjs_content(content)
    if file_urls:
        delete_files_from_urls(file_urls)