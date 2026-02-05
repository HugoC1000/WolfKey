from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from forum.models import User, Course, UserCourseHelp, UserCourseExperience
from forum.forms import CustomUserCreationForm, CustomPasswordResetForm
import json
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.urls import reverse_lazy
from forum.services.auth_services import authenticate_user, register_user
from forum.serializers import CourseSerializer

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        
        if form.is_valid():
            # Get course experience data
            help_courses_raw = request.POST.get('help_courses', '').split(',')
            experience_courses_raw = request.POST.get('experience_courses', '').split(',')
            
            # Convert to integers, filtering out invalid values
            help_courses = [int(course_id) for course_id in help_courses_raw if course_id.strip().isdigit()]
            experience_courses = [int(course_id) for course_id in experience_courses_raw if course_id.strip().isdigit()]
            
            # Get preference settings (default to True if not present)
            allow_schedule_comparison = request.POST.get('allow_schedule_comparison') == 'on'
            allow_grade_updates = request.POST.get('allow_grade_updates') == 'on'
            
            # Get schedule data
            schedule_data = {}
            blocks = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
            for block in blocks:
                block_course = request.POST.get(f'block_{block}', '')
                if block_course:
                    try:
                        schedule_data[f'block_{block}'] = int(block_course)
                    except (ValueError, TypeError):
                        # Skip invalid course IDs
                        pass
            
            user, error = register_user(
                request, form, help_courses, experience_courses, 
                schedule_data,
                allow_schedule_comparison, allow_grade_updates
            )
            if error:
                messages.error(request, error)
            else:
                messages.success(request, 'Welcome to WolfKey!')
                return redirect('all_posts')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        field_name = form.fields[field].label or field.replace('_', ' ').title()
                        messages.error(request, f"{field_name}: {error}")
        
        help_course_ids = request.POST.get('help_courses', '').split(',')
        experience_course_ids = request.POST.get('experience_courses', '').split(',')

        help_course_ids = [int(id) for id in help_course_ids if id.isdigit()]
        experience_course_ids = [int(id) for id in experience_course_ids if id.isdigit()]

        help_courses_queryset = Course.objects.filter(id__in=help_course_ids)
        experience_courses_queryset = Course.objects.filter(id__in=experience_course_ids)
        
        help_courses = CourseSerializer(help_courses_queryset, many=True).data
        experience_courses = CourseSerializer(experience_courses_queryset, many=True).data
        
        # Build schedule data in BlockSerializer format for form re-rendering
        schedule_data = {}
        blocks = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
        for block in blocks:
            block_course = request.POST.get(f'block_{block}', '')
            if block_course:
                try:
                    course = Course.objects.get(id=int(block_course))
                    schedule_data[block] = {
                        'course': course.name,
                        'course_id': course.id,
                    }
                except (Course.DoesNotExist, ValueError):
                    schedule_data[block] = {
                        'course': None,
                        'course_id': None,
                    }
            else:
                schedule_data[block] = {
                    'course': None,
                    'course_id': None,
                }

        return render(request, 'forum/register.html', {
            'form': form,
            'courses': Course.objects.all().order_by('name'),
            'form_errors': form.errors.as_json(),
            'selected_help_courses': json.dumps(help_courses),
            'selected_experience_courses': json.dumps(experience_courses),
            'saved_schedule_data': json.dumps(schedule_data)
        })
    else:
        form = CustomUserCreationForm()

    courses = Course.objects.all().order_by('name')
    return render(request, 'forum/register.html', {
        'form': form,
        'courses': courses
    })

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            school_email = form.cleaned_data.get('username')  # AuthenticationForm uses 'username' field
            password = form.cleaned_data.get('password')

            user, error = authenticate_user(request, school_email, password)
            if user:
                login(request,user)
                messages.success(request, 'You are now logged in!')
                return redirect('for_you')
            else:
                form.add_error(None, error)
        else:
            form.add_error(None, "Invalid credentials. Please try again.")
    else:
        form = AuthenticationForm()

    return render(request, 'forum/login.html', {'form': form})


from django.contrib.auth import logout

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('all_posts')

class CustomPasswordResetView(PasswordResetView):
    template_name = 'forum/registration/password_reset.html'
    email_template_name = 'forum/registration/password_reset_email.html'
    html_email_template_name = 'forum/registration/password_reset_email.html'
    success_url = reverse_lazy('password_reset_done')
    form_class = CustomPasswordResetForm

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'forum/registration/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'forum/registration/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'forum/registration/password_reset_complete.html'