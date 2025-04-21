from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from forum.forms import UserUpdateForm

from forum.models import User 
from forum.models import Post, Solution 
from forum.models import ( 
    UserCourseExperience, 
    UserCourseHelp,
    UserProfile
)

from forum.forms import ( 
    UserCourseExperienceForm,
    UserCourseHelpForm,
    UserProfileForm
)

from forum.views.utils import (
    detect_bad_words
)

@login_required
def profile_view(request, username):
    profile_user = get_object_or_404(User, username=username)
    recent_posts = Post.objects.filter(author=profile_user).order_by('-created_at')[:5]
    posts_count = Post.objects.filter(author=profile_user).count()
    solutions_count = Solution.objects.filter(author=profile_user).count()

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.personal_email = request.POST.get('personal_email', request.user.personal_email)
        request.user.phone_number = request.POST.get('phone_number', request.user.phone_number)
        request.user.save()

        if 'bio' in request.POST:
            bio = request.POST.get('bio', profile_user.userprofile.bio)
            try:
                detect_bad_words(bio)  # Check for bad words
                profile_user.userprofile.bio = bio
                profile_user.userprofile.save()
            except ValueError as e:
                messages.error(request, str(e))

        # Update background hue
        hue_value = request.POST.get('background_hue', profile_user.userprofile.background_hue)
        profile_user.userprofile.background_hue = int(hue_value)
        profile_user.userprofile.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('profile', username=request.user.username)

    context = {
        'profile_user': profile_user,
        'recent_posts': recent_posts,
        'experience_form': UserCourseExperienceForm(user=profile_user),
        'help_form': UserCourseHelpForm(user=profile_user),
        'posts_count': posts_count,
        'solutions_count': solutions_count,
        'experienced_courses': UserCourseExperience.objects.filter(user=profile_user),
        'help_needed_courses': UserCourseHelp.objects.filter(user=profile_user, active=True),
    }
    return render(request, 'forum/profile.html', context)

@login_required
def edit_profile(request):
    try:
        profile = request.user.userprofile
    except ObjectDoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile', username=request.user.username)
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'forum/edit_profile.html', {'form': form})

@login_required
def my_profile(request):
    return redirect('profile', username=request.user.username)


@login_required
def add_experience(request):
    if request.method == 'POST':
        form = UserCourseExperienceForm(request.POST, user=request.user) 
        if form.is_valid():
            experience = form.save(commit=False)
            experience.user = request.user
            experience.save()
            messages.success(request, 'Course experience added successfully!')
    return redirect('profile', username=request.user.username) 

@login_required
def add_help_request(request):
    if request.method == 'POST':
        form = UserCourseHelpForm(request.POST, user=request.user)  
        if form.is_valid():
            help_request = form.save(commit=False)
            help_request.user = request.user
            help_request.save()
            messages.success(request, 'Help request added successfully!')
    return redirect('profile', username=request.user.username) 

@login_required
def remove_experience(request, experience_id):
    try:
        experience = get_object_or_404(UserCourseExperience, 
                                     id=experience_id, 
                                     user=request.user)
        if request.method == 'POST':
            experience.delete()
            messages.success(request, 'Course experience removed successfully!')
    except UserCourseExperience.DoesNotExist:
        messages.error(request, 'Course experience not found.')
    except Exception as e:
        messages.error(request, f'Error removing course experience: {str(e)}')
    
    return redirect('profile', username=request.user.username)

@login_required
def remove_help_request(request, help_id):
    help_request = get_object_or_404(UserCourseHelp, id=help_id, user=request.user)
    if request.method == 'POST':
        help_request.delete()
        messages.success(request, 'Help request removed successfully!')
    return redirect('profile', username=request.user.username)