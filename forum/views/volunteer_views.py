from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from forum.services.volunteer_service import get_volunteer_page_data


@login_required
def volunteer_hours_page(request):
    return render(request, 'forum/volunteer_hours.html', get_volunteer_page_data(request.user))
