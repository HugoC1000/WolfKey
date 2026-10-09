"""Build the standard JSON envelope used by website fetch endpoints."""


def success_payload(data, message=None):
    return {
        'success': True,
        'message': message,
        'data': data,
        'error_code': None,
    }


def error_payload(message, status_code=400, error_code=None):
    if error_code is None:
        error_code = {
            400: 'bad_request',
            401: 'authentication_required',
            403: 'permission_denied',
            404: 'not_found',
            409: 'conflict',
            422: 'validation_error',
        }.get(status_code, 'server_error' if status_code >= 500 else 'request_failed')

    return {
        'success': False,
        'message': str(message),
        'data': None,
        'error_code': error_code,
    }
