from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from forum.models import VolunteerPinMilestone, VolunteerResource
from django.views.decorators.http import require_POST


def is_volunteer_admin(user):
    """Check if user is admin or volunteer coordinator"""
    return user.is_authenticated and (user.is_staff or user.volunteer_coordinator)


@login_required
@user_passes_test(is_volunteer_admin)
def volunteer_admin_page(request):
    """
    Admin page for managing volunteer pin milestones and resources.
    Only accessible by staff or volunteer coordinators.
    """
    milestones = VolunteerPinMilestone.objects.all().order_by('hours_required')
    resources = VolunteerResource.objects.all().order_by('display_order', 'title')
    
    context = {
        'milestones': milestones,
        'resources': resources,
    }
    
    return render(request, 'forum/volunteer_admin.html', context)


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def create_milestone(request):
    """Create a new volunteer pin milestone"""
    try:
        name = request.POST.get('name', '').strip()
        hours_required = request.POST.get('hours_required', '').strip()
        has_other_requirements = request.POST.get('has_other_requirements') == 'on'
        
        if not name or not hours_required:
            messages.error(request, 'Name and hours required are mandatory fields.')
            return redirect('volunteer_admin')
        
        milestone = VolunteerPinMilestone.objects.create(
            name=name,
            hours_required=int(hours_required),
            has_other_requirements=has_other_requirements
        )
        
        messages.success(request, f'Milestone "{milestone.name}" created successfully!')
    except ValueError:
        messages.error(request, 'Invalid hours or order value. Please enter valid numbers.')
    except Exception as e:
        messages.error(request, f'Error creating milestone: {str(e)}')
    
    return redirect('volunteer_admin')


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def update_milestone(request, milestone_id):
    """Update an existing volunteer pin milestone"""
    milestone = get_object_or_404(VolunteerPinMilestone, id=milestone_id)
    
    try:
        name = request.POST.get('name', '').strip()
        hours_required = request.POST.get('hours_required', '').strip()
        has_other_requirements = request.POST.get('has_other_requirements') == 'on'
        
        if not name or not hours_required:
            messages.error(request, 'Name and hours required are mandatory fields.')
            return redirect('volunteer_admin')
        
        milestone.name = name
        milestone.hours_required = int(hours_required)
        milestone.has_other_requirements = has_other_requirements
        milestone.save()
        
        messages.success(request, f'Milestone "{milestone.name}" updated successfully!')
    except ValueError:
        messages.error(request, 'Invalid hours or order value. Please enter valid numbers.')
    except Exception as e:
        messages.error(request, f'Error updating milestone: {str(e)}')
    
    return redirect('volunteer_admin')


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def delete_milestone(request, milestone_id):
    """Delete a volunteer pin milestone"""
    milestone = get_object_or_404(VolunteerPinMilestone, id=milestone_id)
    
    try:
        milestone_name = milestone.name
        milestone.delete()
        messages.success(request, f'Milestone "{milestone_name}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting milestone: {str(e)}')
    
    return redirect('volunteer_admin')


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def create_resource(request):
    """Create a new volunteer resource"""
    try:
        title = request.POST.get('title', '').strip()
        url = request.POST.get('url', '').strip()
        description = request.POST.get('description', '').strip()
        display_order = request.POST.get('display_order', '0').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        if not title or not url:
            messages.error(request, 'Title and URL are mandatory fields.')
            return redirect('volunteer_admin')
        
        resource = VolunteerResource.objects.create(
            title=title,
            url=url,
            description=description,
            display_order=int(display_order),
            is_active=is_active
        )
        
        messages.success(request, f'Resource "{resource.title}" created successfully!')
    except ValueError:
        messages.error(request, 'Invalid display order value. Please enter a valid number.')
    except Exception as e:
        messages.error(request, f'Error creating resource: {str(e)}')
    
    return redirect('volunteer_admin')


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def update_resource(request, resource_id):
    """Update an existing volunteer resource"""
    resource = get_object_or_404(VolunteerResource, id=resource_id)
    
    try:
        title = request.POST.get('title', '').strip()
        url = request.POST.get('url', '').strip()
        description = request.POST.get('description', '').strip()
        display_order = request.POST.get('display_order', '0').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        if not title or not url:
            messages.error(request, 'Title and URL are mandatory fields.')
            return redirect('volunteer_admin')
        
        resource.title = title
        resource.url = url
        resource.description = description
        resource.display_order = int(display_order)
        resource.is_active = is_active
        resource.save()
        
        messages.success(request, f'Resource "{resource.title}" updated successfully!')
    except ValueError:
        messages.error(request, 'Invalid display order value. Please enter a valid number.')
    except Exception as e:
        messages.error(request, f'Error updating resource: {str(e)}')
    
    return redirect('volunteer_admin')


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def delete_resource(request, resource_id):
    """Delete a volunteer resource"""
    resource = get_object_or_404(VolunteerResource, id=resource_id)
    
    try:
        resource_title = resource.title
        resource.delete()
        messages.success(request, f'Resource "{resource_title}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting resource: {str(e)}')
    
    return redirect('volunteer_admin')
