"""One error shape for service actions shared by website and API callers.

Services return their usual data on success. Expected failures return a dict
with ``error`` and ``status``; entry points decide how to display the error.
``status`` is the HTTP status used by both entry points.
"""


def service_error(message, status=400):
    """Describe an action failure without creating an HTTP response."""
    return {'error': str(message), 'status': status}


def service_success(message=None, **data):
    """Return action data, optionally with a message for the caller to show."""
    result = dict(data)
    if message is not None:
        result['message'] = message
    return result
