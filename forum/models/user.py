from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from cryptography.fernet import Fernet
import base64
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
    student_id = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Student ID extracted from school email"
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
    
    is_teacher = models.BooleanField(
        default=False,
        help_text="Indicates if this user is a teacher"
    )
    
    volunteer_coordinator = models.BooleanField(
        default=False,
        help_text="Indicates if this user can manage volunteer hours and milestones"
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
        # Auto-populate student_id from school_email (extract only numbers)
        if self.school_email and not self.student_id:
            import re
            email_prefix = self.school_email.split('@')[0]
            # Extract only numeric characters
            numbers_only = re.sub(r'[^0-9]', '', email_prefix)
            if numbers_only:
                self.student_id = numbers_only
        
        # Auto-generate username if not provided
        if not self.username and self.first_name and self.last_name:
            from forum.services.utils import generate_username
            self.username = generate_username(self.first_name, self.last_name)
        
        super().save(*args, **kwargs)
        search_vector = (
            SearchVector('first_name', weight='A') +
            SearchVector('last_name', weight='A')
        )
        User.objects.filter(id=self.id).update(search_vector=search_vector)


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
        from forum.forms import WolfNetSettingsForm
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

    # Fields for course blocks (using string reference to avoid circular imports)
    block_1A = models.ForeignKey('forum.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name="block_1A")
    block_1B = models.ForeignKey('forum.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name="block_1B")
    block_1D = models.ForeignKey('forum.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name="block_1D")
    block_1E = models.ForeignKey('forum.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name="block_1E")
    block_2A = models.ForeignKey('forum.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name="block_2A")
    block_2B = models.ForeignKey('forum.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name="block_2B")
    block_2C = models.ForeignKey('forum.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name="block_2C")
    block_2D = models.ForeignKey('forum.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name="block_2D")
    block_2E = models.ForeignKey('forum.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name="block_2E")
    
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
