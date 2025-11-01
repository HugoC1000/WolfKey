from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json


@api_view(['POST', 'GET'])
def debug_logs(request):
    """Simple debug endpoint that prints incoming logs/payloads to server stdout.

    POST: expects JSON body (or any body) and will print it.
    GET: will print query params (for quick router-style logging).
    """
    try:
        print('--- /api/debug/logs/ called ---')
        print(f'METHOD: {request.method} PATH: {request.get_full_path()}')

        if request.method == 'POST':
            # Try to get parsed data first (DRF will parse JSON automatically)
            try:
                payload = request.data
            except Exception:
                # Fallback to raw body
                try:
                    payload = json.loads(request.body.decode('utf-8'))
                except Exception:
                    payload = {'raw': request.body.decode('utf-8', errors='replace')}

            print('PAYLOAD:')
            try:
                print(json.dumps(payload, indent=2, default=str))
            except Exception:
                print(payload)

        else:  # GET
            params = request.query_params.dict()
            print('QUERY PARAMS:')
            try:
                print(json.dumps(params, indent=2, default=str))
            except Exception:
                print(params)

        # Also print some basic headers for context
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
        print('FORWARDED_FOR:', forwarded_for)

        print('--- end debug log ---')
        return Response({'received': True}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'Error in debug_logs: {e}')
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
