# decorators.py
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from .models import *

def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'user_id' not in request.session:
            messages.error(request, 'Please login first!')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def role_required(allowed_roles=[]):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if 'user_id' not in request.session:
                messages.error(request, 'Please login first!')
                return redirect('login')
            
            user_role = request.session.get('role')
            if user_role not in allowed_roles:
                messages.error(request, 'You do not have permission to access this page!')
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def check_blocked_user(view_func):
    def wrapper(request, *args, **kwargs):
        # Check if user is logged in via session
        if 'user_id' in request.session and request.session.get('user_type') == 'employee':
            try:
                employee = Employee.objects.get(id=request.session.get('user_id'))
                if employee.is_blocked:
                    # Clear the session and redirect to login with a message
                    request.session.flush()
                    messages.error(request, f'Your account has been blocked by {employee.blocked_by.full_name} on {employee.blocked_at.strftime("%Y-%m-%d %H:%M")}. Please contact the administrator.')
                    return redirect('login')
            except Employee.DoesNotExist:
                # If employee doesn't exist, clear session
                request.session.flush()
                return redirect('login')
        
        return view_func(request, *args, **kwargs)
    return wrapper

