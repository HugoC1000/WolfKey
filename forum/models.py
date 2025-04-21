from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.urls import reverse
import os
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import BaseUserManager
from django.utils import timezone

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
    


class Course(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100, default = "Misc")
    description = models.TextField(blank=True)
    
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
    
class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    tags = models.ManyToManyField(Tag, related_name='posts', blank=True)
    search_vector = SearchVectorField(null=True, blank=True)
    courses = models.ManyToManyField(Course, related_name='posts', blank=True)
    solved = models.BooleanField(default = False)
    
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

    
class SavedPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_posts")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="saves")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Ensure users can't save the same post twice.

    def __str__(self):
        return f"{self.user.username} saved {self.post.title}"

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
    content = models.TextField()
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
        

class Comment(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies') 

    class Meta:
        ordering = ['-created_at']

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    background_hue = models.IntegerField(default=231) 

    def __str__(self):
        return f"{self.user.username}'s profile"
    



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

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('post', 'New Post'),
        ('solution', 'New Solution'),
    )
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, null=True, blank=True)
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