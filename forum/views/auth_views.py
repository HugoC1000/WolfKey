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

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        
        if form.is_valid():
            wolfnet_password = request.POST.get('wolfnet_password', '').strip()
            
            # Get course experience data
            help_courses = request.POST.get('help_courses', '').split(',')
            experience_courses = request.POST.get('experience_courses', '').split(',')
            
            # Get schedule data if WolfNet password was provided
            schedule_data = {}
            blocks = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
            for block in blocks:
                block_course = request.POST.get(f'block_{block}', '')
                if block_course:
                    schedule_data[f'block_{block}'] = block_course
            
            user, error = register_user(request, form, help_courses, experience_courses, wolfnet_password, schedule_data)
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

        help_courses = list(Course.objects.filter(id__in=help_course_ids).values('id', 'name'))
        experience_courses = list(Course.objects.filter(id__in=experience_course_ids).values('id', 'name'))

        wolfnet_password = request.POST.get('wolfnet_password', '').strip()
        
        schedule_data = {}
        blocks = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
        for block in blocks:
            block_course = request.POST.get(f'block_{block}', '')
            if block_course:
                try:
                    course = Course.objects.get(id=int(block_course))
                    schedule_data[block] = {
                        'id': course.id,
                        'name': course.name,
                    }
                except (Course.DoesNotExist, ValueError):
                    pass

        return render(request, 'forum/register.html', {
            'form': form,
            'courses': Course.objects.all().order_by('name'),
            'form_errors': form.errors.as_json(),
            'selected_help_courses': json.dumps(help_courses),
            'selected_experience_courses': json.dumps(experience_courses),
            'saved_wolfnet_password': wolfnet_password,
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