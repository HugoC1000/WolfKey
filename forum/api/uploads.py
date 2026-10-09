from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from forum.services.utils import store_editor_image


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_upload_image(request):
    result = store_editor_image(request.FILES.get('image'))
    if 'error' in result:
        return Response({'error': result['error']}, status=result['status'])
    return Response({'success': 1, 'file': {'url': result['url']}})
