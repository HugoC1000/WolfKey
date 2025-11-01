from django.shortcuts import render

def privacy_view(request):
    """
    Render the Privacy Policy page for the WolfKey platform.
    """
    return render(request, 'forum/privacy.html')
