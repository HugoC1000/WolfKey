from django import forms
from .models import Post, Comment, Solution, File, UserProfile, UserCourseExperience, UserCourseHelp, Course, User
from django.forms.widgets import ClearableFileInput
from django.core.files.uploadedfile import UploadedFile
from django.contrib.auth.forms import UserCreationForm
from django.db.models import F, Q
import re
import json
import uuid
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password
from cryptography.fernet import Fernet
import base64
import logging

logger = logging.getLogger(__name__)

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

        
class PostForm(forms.ModelForm):

    is_anonymous = forms.BooleanField(
        required=False, label="Post Anonymously",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    class Meta:
        model = Post
        fields = ['title', 'content', 'courses', 'is_anonymous']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_courses(self):
        courses = self.cleaned_data.get('courses')
        if not courses:
            return []

        course_ids = []
        for course in courses:
            try:
                if isinstance(course, str):
                    if course.startswith('[') and course.endswith(']'):
                        parsed_ids = json.loads(course)
                        course_ids.extend(parsed_ids)
                    else:
                        course_ids.append(int(course))
                else:
                    course_ids.append(course.id if hasattr(course, 'id') else int(course))
            except (ValueError, json.JSONDecodeError):
                continue

        course_ids = list(set(course_ids))
        return Course.objects.filter(id__in=course_ids)

    def clean(self):
        cleaned_data = super().clean()
        if 'content' not in self.data:
            raise forms.ValidationError("Content is required")
        return cleaned_data

class SolutionForm(forms.ModelForm):
    class Meta:
        model = Solution
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write your solution here...'}),
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Write your comment here...'}),
        }

    def clean_content(self):
        data = self.cleaned_data['content']
        if not isinstance(data, dict):  # Ensure content is valid JSON
            raise forms.ValidationError("Invalid content format.")
        return data


class UserProfileForm(forms.ModelForm):
    instagram_handle = forms.CharField(
        max_length=30,
        required=False,
        help_text="Your Instagram username (without @)",
        widget=forms.TextInput(attrs={
            'placeholder': 'username',
            'class': 'form-control'
        })
    )
    snapchat_handle = forms.CharField(
        max_length=15,
        required=False,
        help_text="Your Snapchat username (without @)",
        widget=forms.TextInput(attrs={
            'placeholder': 'username',
            'class': 'form-control'
        })
    )
    linkedin_url = forms.URLField(
        max_length=200,
        required=False,
        help_text="Your LinkedIn profile URL (e.g., https://www.linkedin.com/in/yourprofile)",
        widget=forms.URLInput(attrs={
            'placeholder': 'https://www.linkedin.com/in/yourprofile',
            'class': 'form-control'
        })
    )
    
    class Meta:
        model = UserProfile
        fields = ['bio', 'instagram_handle', 'snapchat_handle', 'linkedin_url']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }
    
    def clean_instagram_handle(self):
        """Clean and validate Instagram handle"""
        handle = self.cleaned_data.get('instagram_handle', '').strip()
        if handle:
            # Remove @ symbol if present
            handle = handle.lstrip('@')
            # Validate format (alphanumeric, dots, underscores only)
            if not all(c.isalnum() or c in '._' for c in handle):
                raise forms.ValidationError('Instagram username can only contain letters, numbers, dots, and underscores.')
        return handle if handle else None
    
    def clean_snapchat_handle(self):
        """Clean and validate Snapchat handle"""
        handle = self.cleaned_data.get('snapchat_handle', '').strip()
        if handle:
            # Remove @ symbol if present
            handle = handle.lstrip('@')
            # Validate format (alphanumeric, dots, underscores, hyphens)
            if not all(c.isalnum() or c in '._-' for c in handle):
                raise forms.ValidationError('Snapchat username can only contain letters, numbers, dots, underscores, and hyphens.')
        return handle if handle else None
    
    def clean_linkedin_url(self):
        """Validate LinkedIn URL format"""
        url = self.cleaned_data.get('linkedin_url', '').strip()
        if url:
            # Ensure it starts with the correct format
            if not (url.startswith('https://www.linkedin.com/in/') or 
                    url.startswith('http://www.linkedin.com/in/') or
                    url.startswith('www.linkedin.com/in/')):
                raise forms.ValidationError('LinkedIn URL must start with www.linkedin.com/in/')
            
            # Ensure https protocol
            if url.startswith('www.'):
                url = 'https://' + url
            elif url.startswith('http://'):
                url = url.replace('http://', 'https://')
        return url if url else None

class UserCourseExperienceForm(forms.ModelForm):
    class Meta:
        model = UserCourseExperience
        fields = ['course']
        widgets = {
            'course': forms.Select(attrs={
                'class': 'form-select',
                'placeholder': 'Select a course'
            })
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            existing_courses = UserCourseExperience.objects.filter(
                user=user
            ).values_list('course', flat=True)
            self.fields['course'].queryset = Course.objects.exclude(
                id__in=existing_courses
            ).order_by('name') 

class UserCourseHelpForm(forms.ModelForm):
    class Meta:
        model = UserCourseHelp
        fields = ['course']
        widgets = {
            'course': forms.Select(attrs={
                'class': 'form-select',
                'placeholder': 'Select a course'
            })
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            existing_help = UserCourseHelp.objects.filter(
                user=user, 
                active=True
            ).values_list('course', flat=True)
            self.fields['course'].queryset = Course.objects.exclude(
                id__in=existing_help
            ).order_by('name')


class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        }),
        help_text="Required. Enter your first name."
    )
    
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        }),
        help_text="Required. Enter your last name."
    )

    school_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'school@wpga.ca'
        }),
        help_text="Must be a valid @wpga.ca email address"
    )
    personal_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'personal@example.com'
        }),
        help_text="<strong> Optional </strong> personal email address. NOTE: You can not reset your password without this!"
    )

    class Meta:
        model = User
        # grade_level is stored on UserProfile, but we expose it on the registration form
        fields = ('first_name', 'last_name', 'school_email', 'personal_email', 'password1', 'password2')

    GRADE_CHOICES = [('', 'Select grade'), ('8', '8'), ('9', '9'), ('10', '10'), ('11', '11'), ('12', '12'),('13', '13')] # 13 is alumni

    grade_level = forms.ChoiceField(
        required=False,
        choices=GRADE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_grade_level'
        }),
        help_text='Your current grade level (8 - 13 for alumni). If in summer, grade level in Sept'
    )

    def clean_school_email(self):
        email = self.cleaned_data.get('school_email')
        if not email.endswith('@wpga.ca'):
            raise forms.ValidationError("School email must end with @wpga.ca")
        if User.objects.filter(school_email=email).exists():
            raise forms.ValidationError("This school email is already registered")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = str(uuid.uuid4())[:30]

        if commit:
            user.save()

        if not user.personal_email:
            user.personal_email = user.school_email
        # Save grade_level to the related UserProfile if provided
        grade_val = self.cleaned_data.get('grade_level')
        try:
            # grade_level on profile is IntegerField, allow blank
            if grade_val is not None and grade_val != '':
                user.userprofile.grade_level = int(grade_val)
                user.userprofile.save()
        except Exception:
            # If profile doesn't exist yet or conversion fails, ignore silently
            pass

        return user

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'personal_email', 'phone_number']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'personal_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

class CustomPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        email = self.cleaned_data['email']
        try:
            user = User.objects.get(school_email=email) if email.endswith('@wpga.ca') else User.objects.get(personal_email=email)
        except User.DoesNotExist:
            raise ValidationError("No account found with this email address.")
        
        return email

    def get_users(self, email):
        if email.endswith('@wpga.ca'):
            return User.objects.filter(school_email=email, is_active=True)
        return User.objects.filter(personal_email=email, is_active=True)

    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        subject = render_to_string(subject_template_name, context).strip().replace('\n', '')
        body = render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name:
            html_email = render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, 'text/html')

        email_message.send()

    def save(self, domain_override=None,
             use_https=False, token_generator=default_token_generator,
             request=None, **kwargs):
        email = self.cleaned_data["email"]
        for user in self.get_users(email):
            to_email = user.personal_email if email.endswith('@wpga.ca') else user.personal_email

            context = {
                "email": to_email,
                "domain": domain_override or request.get_host(),
                "site_name": "WolfKey",
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "user": user,
                "token": token_generator.make_token(user),
                "protocol": "https" if use_https else "http",
                **(kwargs.get("extra_email_context") or {})
            }

            self.send_mail(
                subject_template_name=kwargs.get('subject_template_name', 'registration/password_reset_subject.txt'),
                email_template_name=kwargs.get('email_template_name', 'forum/registration/password_reset_email.html'),
                context=context,
                from_email=kwargs.get('from_email', settings.DEFAULT_FROM_EMAIL),
                to_email=to_email,
                html_email_template_name=kwargs.get('html_email_template_name'),
            )
