from .models import UpdateAnnouncement, UserUpdateView, UserProfile, User

def notifications(request):
    if request.user.is_authenticated:
        notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:5]
        return {
            'notifications': notifications,
            'unread_notifications_count': notifications.count()
        }
    return {}

def latest_update(request):
    if not request.user.is_authenticated:
        return {'latest_update': None}
    
    # Get the latest active update
    latest = UpdateAnnouncement.objects.filter(is_active=True).first()
    
    if not latest:
        return {'latest_update': None}
    
    # Check if user has already viewed this update
    has_viewed = UserUpdateView.objects.filter(
        user=request.user,
        update=latest
    ).exists()
    
    return {
        'latest_update': latest if not has_viewed else None
    }

def user_background_slider(request):
    if request.user.is_authenticated:
        try:
            return {'background_hue': request.user.userprofile.background_hue}
        except UserProfile.DoesNotExist:
            return {'background_hue': 231}  # Default value
    return {'background_hue': 231}  # Default value for unauthenticated users

def user_count(request):
    return {
        'user_count': User.objects.count()
    }