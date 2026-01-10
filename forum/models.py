from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.urls import reverse
import os
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import BaseUserManager
from django.utils import timezone
import base64
from django.conf import settings
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

class UserManager(BaseUserManager):
    def create_user(self, school_email, first_name, last_name, password=None, **extra_fields):
        if not school_email:
            raise ValueError('The School Email field must be set')
        
        email = self.normalize_email(school_email)
        user = self.model(
            school_email=email,
            first_name=first_name,
            last_name=last_name,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, school_email, first_name, last_name, password=None, username=None, **extra_fields):
        """
        Create and save a SuperUser with the given email, first name, last name and password.
        The username parameter is accepted but ignored as we don't use it.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        return self.create_user(
            school_email=school_email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            **extra_fields
        )
        
class User(AbstractUser):
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True
    )

    first_name = models.CharField(
        max_length=150,
        blank=False,
        null=False,
        help_text="Required. Enter your first name."
    )
    last_name = models.CharField(
        max_length=150,
        blank=False,
        null=False,
        help_text="Required. Enter your last name."
    )
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='forum_users',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='forum_users',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )
    school_email = models.EmailField(
        unique=True,
        help_text="Must be a valid @wpga.ca email address",
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9._%+-]+@wpga\.ca$',
                message="Email must be a valid @wpga.ca address"
            )
        ]
    )
    personal_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Optional personal email address"
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ],
        help_text="Optional phone number in international format (e.g., +12345678900)"
    )
    
    objects = UserManager()

    USERNAME_FIELD = 'school_email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_absolute_url(self):
        return reverse('profile', args=[str(self.username)]) 
    
    search_vector = SearchVectorField(null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        search_vector = (
            SearchVector('first_name', weight='A') +
            SearchVector('last_name', weight='A')
        )
        User.objects.filter(id=self.id).update(search_vector=search_vector)

class GradebookSnapshot(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='gradebook_snapshots')
    section_id = models.CharField(max_length=32)
    marking_period_id = models.CharField(max_length=32)
    json_data = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'section_id', 'marking_period_id', 'timestamp')

    def __str__(self):
        return f"Snapshot for {self.user.school_email} | Section {self.section_id} | MP {self.marking_period_id} @ {self.timestamp}"
    
class Block(models.Model):
    code = models.CharField(max_length=8, unique=True)  # e.g. '1A', '2C'
    label = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.code

class Course(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100, default = "Misc")
    description = models.TextField(blank=True)
    # Maximum grade level eligible for this course (e.g., 12). If null, course is available to all grades.
    max_grade = models.IntegerField(null=True, blank=True)
    blocks = models.ManyToManyField(Block, blank=True, related_name='courses')
    
    def __str__(self):
        return f"{self.name}"
    
class CourseAlias(models.Model):
    name = models.CharField(max_length=100)
    course = models.ForeignKey(Course, related_name='aliases', on_delete=models.CASCADE)
    
class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    search_vector = SearchVectorField(null=True, blank=True)
    courses = models.ManyToManyField(Course, related_name='posts', blank=True)
    solved = models.BooleanField(default = False)
    views = models.IntegerField(default = 0)
    is_anonymous = models.BooleanField(default=False)
    
    accepted_solution = models.OneToOneField(
        'Solution',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='accepted_for'
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        search_vector = (
            SearchVector('title', weight='A') +
            SearchVector('content', weight='B')
        )
        Post.objects.filter(id=self.id).update(search_vector=search_vector)

    def get_absolute_url(self):
        return reverse('post_detail', args=[self.id])

    def like_count(self):
        return self.likes.count()

    def is_liked_by(self, user):
        if not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists()
    
    def get_author(self, ignore_anonymous=False):
        """Return author object with anonymous profile picture if post is anonymous
        
        Args:
            ignore_anonymous: If True, return actual author info even for anonymous posts.
                            If False (default), return anonymous indicator for anonymous posts.
        """
        if self.is_anonymous and not ignore_anonymous:
            # Return anonymous indicator for anonymous posts
            return {
                'user': self.author,
                'is_anonymous': True
            }
        return {
            'user': self.author,
            'is_anonymous': False
        }
    
    def get_first_image_url(self):
        """Extract the first image URL from the post content JSON"""
        try:
            import json
            
            content = self.content
            if isinstance(content, str):
                content = json.loads(content)
            
            if not isinstance(content, dict) or 'blocks' not in content:
                return None
            
            for block in content.get('blocks', []):
                if isinstance(block, dict) and block.get('type') == 'image':
                    if 'data' in block and 'file' in block['data']:
                        file_data = block['data']['file']
                        if isinstance(file_data, dict) and 'url' in file_data:
                            return file_data['url']
                        elif isinstance(file_data, str):
                            return file_data
            
            return None
            
        except (json.JSONDecodeError, AttributeError, TypeError):
            return None
    
class SavedPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_posts")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="saves")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Ensure users can't save the same post twice.

    def __str__(self):
        return f"{self.user.username} saved {self.post.title}"

class FollowedPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followed_posts")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="followers")
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Ensure users can't follow the same post twice.

    def __str__(self):
        return f"{self.user.username} follows {self.post.title}"

class File(models.Model):
    post = models.ForeignKey('Post', related_name='files', on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(upload_to='uploads/')
    temporary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    upload_session = models.CharField(max_length=100, blank=True)
    
    def delete(self, *args, **kwargs):
        # Delete actual file when model is deleted
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.file.name}"
    
    @property
    def filename(self):
        return os.path.basename(self.file.name)

class Solution(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='solutions')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)

    def __str__(self):
        return f'Solution by {self.author.username} for {self.post.title}'
    
    def get_absolute_url(self):
        """
        Returns the URL to the specific solution element on the post detail page.
        """
        return f"{self.post.get_absolute_url()}#solution-{self.id}"
    
    def root_comments_count(self):
        return self.comments.filter(parent__isnull=True).count()

        

class SavedSolution(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_solutions")
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name="saves")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'solution')  # Ensure users can't save the same solution twice.

    def __str__(self):
        return f"{self.user.username} saved solution for {self.solution.post.title}"

class Comment(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies') 

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment by {self.author.username}'
    
    @property
    def replies(self):
        return Comment.objects.filter(parent=self).order_by('created_at')
    
    def get_absolute_url(self):
        return f'#comment-{self.id}'
    
    def get_depth(self):
        """Calculate the nesting depth of this comment"""
        depth = 0
        parent = self.parent
        while parent:
            depth += 1
            parent = parent.parent
        return min(depth, 5)  # Limit maximum nesting depth to 5

class SolutionUpvote(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('solution', 'user')

class SolutionDownvote(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('solution', 'user')

class CommentUpvote(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('comment', 'user')

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    points = models.IntegerField(default=0)
    is_moderator = models.BooleanField(default=False)
    # Grade level for the user (e.g., 9, 10, 11, 12). Nullable for staff or unknown.
    grade_level = models.IntegerField(null=True, blank=True, help_text="User's current grade level (e.g., 11)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    background_hue = models.IntegerField(default=231)
    
    # WolfNet Integration
    wolfnet_password = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Your WolfNet password for grade notifications and schedule integration"
    )

    def get_decrypted_wolfnet_password(self):
        """Get the decrypted WolfNet password for use in web scraping"""
        from .forms import WolfNetSettingsForm
        return WolfNetSettingsForm.decrypt_password(self.wolfnet_password)
    
    def save(self, *args, **kwargs):
        if self.wolfnet_password and not self.wolfnet_password.startswith('gAAAA'):  # Fernet tokens start with 'gAAAA'
            key = base64.urlsafe_b64encode(settings.SECRET_KEY[:32].encode())
            f = Fernet(key)
            self.wolfnet_password = f.encrypt(self.wolfnet_password.encode()).decode()
        super().save(*args, **kwargs)

    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        default='profile_pictures/default.png',
        blank=True,
        null=True
    )
    
    lunch_card = models.ImageField(
        upload_to='lunch_cards/',
        blank=True,
        null=True,
        help_text="Upload your lunch card image"
    )

    #Fields for course blocks
    block_1A = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="block_1A")
    block_1B = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="block_1B")
    block_1D = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="block_1D")
    block_1E = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="block_1E")
    block_2A = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="block_2A")
    block_2B = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="block_2B")
    block_2C = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="block_2C")
    block_2D = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="block_2D")
    block_2E = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="block_2E")
    
    # Expo push notification token for mobile app
    expo_push_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Expo push notification token for mobile app notifications"
    )
    
    # User Preferences
    allow_schedule_comparison = models.BooleanField(
        default=True,
        help_text="Allow other users to view and compare your course schedule"
    )
    allow_grade_updates = models.BooleanField(
        default=True,
        help_text="Enable automatic grade notifications from WolfNet"
    )
    display_email = models.BooleanField(
        default=False,
        help_text="Display your email address on your public profile"
    )
    
    # Social Media Links
    instagram_handle = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text="Your Instagram username (without @)"
    )
    snapchat_handle = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Your Snapchat username (without @)"
    )
    linkedin_url = models.URLField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Your LinkedIn profile URL (must start with www.linkedin.com/in/)"
    )

    def __str__(self):
        return f"{self.user.username}'s profile"
    
    def get_instagram_url(self):
        """Get the full Instagram profile URL"""
        if self.instagram_handle:
            return f"https://www.instagram.com/{self.instagram_handle.strip().lstrip('@')}"
        return None
    
    def get_snapchat_url(self):
        """Get the full Snapchat profile URL"""
        if self.snapchat_handle:
            return f"https://www.snapchat.com/add/{self.snapchat_handle.strip().lstrip('@')}"
        return None
    
    def get_linkedin_url(self):
        """Get the LinkedIn profile URL (already validated)"""
        return self.linkedin_url if self.linkedin_url else None

class DailySchedule(models.Model):
    date = models.DateField(unique=True)
    block_1 = models.CharField(max_length=100, blank=True, null=True)
    block_1_time = models.CharField(max_length=50, blank=True, null=True) 
    block_2 = models.CharField(max_length=100, blank=True, null=True)
    block_2_time = models.CharField(max_length=50, blank=True, null=True)
    block_3 = models.CharField(max_length=100, blank=True, null=True)
    block_3_time = models.CharField(max_length=50, blank=True, null=True)
    block_4 = models.CharField(max_length=100, blank=True, null=True)
    block_4_time = models.CharField(max_length=50, blank=True, null=True)
    block_5 = models.CharField(max_length=100, blank=True, null=True)
    block_5_time = models.CharField(max_length=50, blank=True, null=True)
    block_6 = models.CharField(max_length=100, blank=True, null=True) # Following blocks are only in case of days where there are more than 5 blocks. 
    block_6_time = models.CharField(max_length=50, blank=True, null=True)
    block_7 = models.CharField(max_length=100, blank=True, null=True)
    block_7_time = models.CharField(max_length=50, blank=True, null=True)
    block_8 = models.CharField(max_length=100, blank=True, null=True)
    block_8_time = models.CharField(max_length=50, blank=True, null=True)
    block_9 = models.CharField(max_length=100, blank=True, null=True)
    block_9_time = models.CharField(max_length=50, blank=True, null=True)
    block_10 = models.CharField(max_length=100, blank=True, null=True)
    block_10_time = models.CharField(max_length=50, blank=True, null=True)
    ceremonial_uniform = models.BooleanField(null = True)
    is_school = models.BooleanField(null = True)
    early_dismissal = models.BooleanField(null=True)
    late_start = models.BooleanField(null=True)

    def __str__(self):
        return f"Schedule for {self.date}"

class UserCourseExperience(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='experienced_courses')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'course']

class UserCourseHelp(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='help_needed_courses')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'course']


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a new User is created"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile when the User is saved"""
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)

@receiver(pre_delete, sender='forum.Solution')
def delete_solution_files(sender, instance, **kwargs):
    """Delete files referenced in solution content before deleting the solution"""
    if instance.content:
        from forum.services.utils import extract_and_delete_files_from_content
        try:
            extract_and_delete_files_from_content(instance.content)
        except Exception as e:
            logger.error(f"Error deleting files for solution {instance.id}: {str(e)}")

@receiver(pre_delete, sender='forum.Comment')
def delete_comment_files(sender, instance, **kwargs):
    """Delete files referenced in comment content before deleting the comment"""
    if instance.content:
        from forum.services.utils import extract_and_delete_files_from_content
        try:
            extract_and_delete_files_from_content(instance.content)
        except Exception as e:
            logger.error(f"Error deleting files for comment {instance.id}: {str(e)}")

@receiver(pre_delete, sender='forum.Post')
def delete_post_files(sender, instance, **kwargs):
    """Delete files referenced in post content before deleting the post"""
    if instance.content:
        from forum.services.utils import extract_and_delete_files_from_content
        try:
            extract_and_delete_files_from_content(instance.content)
        except Exception as e:
            logger.error(f"Error deleting files for post {instance.id}: {str(e)}")

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('post', 'New Post'),
        ('solution', 'New Solution'),
        ('comment', 'New Comment'),
        ('reply', 'New Reply'),
        ('grade_update', 'Grade Update'),
        ('edit', 'Post Edit'),
    )
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        
class UpdateAnnouncement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    version = models.CharField(max_length=20)  # e.g., "1.2.0"
    release_date = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-release_date']

class UserUpdateView(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    update = models.ForeignKey(UpdateAnnouncement, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'update']

class PostLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="liked_posts")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} likes {self.post.title}"