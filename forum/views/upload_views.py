from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from forum.services.utils import store_editor_image


@csrf_exempt
def upload_image(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'No image uploaded'}, status=400)

    result = store_editor_image(request.FILES.get('image'))
    if 'error' in result:
        return JsonResponse({'error': result['error']}, status=result['status'])
    return JsonResponse({'success': 1, 'file': {'url': result['url']}})
