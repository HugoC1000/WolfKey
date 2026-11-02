from .models import UserProfile, User


def analytics(request):
    from forum.services.analytics_service import WEB_SCREENS
    if not request.user.is_authenticated or not request.resolver_match:
        return {}
    screen = WEB_SCREENS.get(request.resolver_match.url_name)
    return {'analytics_screen': screen} if screen else {}

def notifications(request):
    if request.user.is_authenticated:
        notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:5]
        return {
            'notifications': notifications,
            'unread_notifications_count': notifications.count()
        }
    return {}

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
