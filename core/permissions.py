from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def require_capability(capability_name):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not getattr(request.user, capability_name, False):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
