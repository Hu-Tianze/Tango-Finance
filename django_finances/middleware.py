import threading

_thread_local = threading.local()


def get_current_request():
    return getattr(_thread_local, 'request', None)


class CurrentRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_local.request = request
        try:
            response = self.get_response(request)
        finally:
            _thread_local.request = None
        return response
