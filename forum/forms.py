from django import forms
from .models import Post, Comment, Solution, Tag, File, UserProfile, UserCourseExperience, UserCourseHelp, Course, User
from django.forms.widgets import ClearableFileInput
from django.core.files.uploadedfile import UploadedFile
from django.contrib.auth.forms import UserCreationForm


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
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.all(),
        required=False
    )
    files = MultipleFileField(widget=MultipleFileInput, required=False)

    class Meta:
        model = Post
        fields = ['title', 'content', 'tags', 'courses']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }

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
        
class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }

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
            )

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
            )


class CustomUserCreationForm(UserCreationForm):
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
        help_text="Optional personal email address"
    )
    phone_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1234567890'
        }),
        help_text="Optional phone number in international format (e.g., +12345678900)"
    )

    class Meta:
        model = User
        fields = ('username', 'school_email', 'personal_email', 'phone_number', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_school_email(self):
        email = self.cleaned_data.get('school_email')
        if not email.endswith('@wpga.ca'):
            raise forms.ValidationError("School email must end with @wpga.ca")
        if User.objects.filter(school_email=email).exists():
            raise forms.ValidationError("This school email is already registered")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Remove any spaces or special characters except +
            phone = ''.join(c for c in phone if c.isdigit() or c == '+')
            # Validate phone number format
            if not re.match(r'^\+?1?\d{9,15}$', phone):
                raise forms.ValidationError("Please enter a valid phone number in international format")
        return phone