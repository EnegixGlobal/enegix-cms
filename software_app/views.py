from django.shortcuts import render, redirect, get_object_or_404
from .models import *
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db import transaction
from .decorators import login_required, role_required, check_blocked_user
from datetime import date, timedelta, datetime, time
import calendar
from django.utils import timezone
from decimal import Decimal
import math
from django.db.models import Sum, Q
from django.views.decorators.csrf import csrf_exempt
import json
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger




def login_view(request):
    # Agar already logged in hai to dashboard pe bhej do
    if 'user_id' in request.session:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # 🔥 PEHLE EMPLOYEE CHECK KARO (Admin bhi ab Employee table mein hai)
        try:
            employee = Employee.objects.get(username=username, is_active=True)
            
            # 🔥 CHECK IF EMPLOYEE IS BLOCKED
            if employee.is_blocked:
                messages.error(request, f'Your account has been blocked by {employee.blocked_by.full_name} on {employee.blocked_at.strftime("%Y-%m-%d %H:%M")}. Please contact the administrator.')
                return render(request, 'login.html')
            
            if password == employee.password:  # Direct password match
                # Session set karo
                request.session['user_id'] = employee.id
                request.session['user_type'] = 'employee'
                request.session['full_name'] = employee.full_name
                request.session['role'] = employee.role  # Can be: admin, hr, sales, developer, seos
                request.session['email'] = employee.email
                request.session['employee_id'] = employee.employee_id
                
                messages.success(request, f'Welcome {employee.full_name}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid password!')
                return render(request, 'login.html')
        except Employee.DoesNotExist:
            pass
        
        # 🔥 AGAR EMPLOYEE NAHI MILA TO SUPER ADMIN CHECK KARO (Only super_admin in AdminUser)
        try:
            admin = AdminUser.objects.get(username=username, is_active=True)
            if password == admin.password:  # Direct password match
                # Session set karo
                request.session['user_id'] = admin.id
                request.session['user_type'] = 'super_admin'  # Changed from 'admin'
                request.session['full_name'] = admin.full_name
                request.session['role'] = admin.role  # Will be 'super_admin'
                request.session['email'] = admin.email
                
                messages.success(request, f'Welcome {admin.full_name}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid password!')
        except AdminUser.DoesNotExist:
            messages.error(request, 'User not found!')
    
    return render(request, 'login.html')

# Logout
def logout_view(request):
    request.session.flush()
    messages.success(request, 'Logged out successfully!')
    return redirect('login')

# UPDATED DASHBOARD - Admin bhi Employee table se fetch hoga
@check_blocked_user
def dashboard(request):
    # Check if logged in
    if 'user_id' not in request.session:
        messages.error(request, 'Please login first!')
        return redirect('login')
    
    role = request.session.get('role')
    user_type = request.session.get('user_type')
    user_id = request.session.get('user_id')
    
    # 🔥 User details fetch karo
    if user_type == 'super_admin':  # Only super_admin from AdminUser table
        user = AdminUser.objects.get(id=user_id)
    else:  # All employees (admin, hr, sales, developer, seos)
        user = Employee.objects.get(id=user_id)
    
    context = {
        'user': user,
        'role': role,
        'user_type': user_type
    }
    
    # Get current month/year
    today = date.today()
    current_month = today.month
    current_year = today.year
    
    # ==================== SUPER ADMIN DASHBOARD ====================
    if role == 'super_admin':
        # Super Admin Stats
        context['total_employees'] = Employee.objects.filter(is_active=True).count()
        context['active_projects'] = Project.objects.filter(is_active=True, status__in=['pending', 'in_progress']).count()
        context['total_clients'] = Client.objects.filter(is_active=True).count()
        context['interested_clients'] = Client.objects.filter(status='interested', is_active=True).count()
        
        # Department wise count (including admin)
        context['admin_count'] = Employee.objects.filter(role='admin', is_active=True).count()  # 🔥 NEW
        context['hr_count'] = Employee.objects.filter(role='hr', is_active=True).count()
        context['developers_count'] = Employee.objects.filter(role='developer', is_active=True).count()
        context['seo_count'] = Employee.objects.filter(role='seos', is_active=True).count()
        context['sales_count'] = Employee.objects.filter(role='sales', is_active=True).count()
        
        # Project status breakdown
        context['completed_projects'] = Project.objects.filter(status='completed').count()
        context['inprogress_projects'] = Project.objects.filter(status='in_progress').count()
        context['pending_projects'] = Project.objects.filter(status='pending').count()
        context['onhold_projects'] = Project.objects.filter(status='on_hold').count()
        
        # Monthly attendance for last 6 months
        attendance_data = []
        for i in range(5, -1, -1):
            month = current_month - i
            year = current_year
            if month <= 0:
                month += 12
                year -= 1
            
            start_date = date(year, month, 1)
            end_date = date(year, month, calendar.monthrange(year, month)[1])
            
            total_att = Attendance.objects.filter(attendance_date__range=[start_date, end_date])
            attendance_data.append({
                'month': calendar.month_abbr[month],
                'present': total_att.filter(status='present').count(),
                'absent': total_att.filter(status='absent').count(),
                'leaves': total_att.filter(status='on_leave').count()
            })
        context['attendance_chart_data'] = json.dumps(attendance_data)
        
        # Recent activities
        recent_projects = Project.objects.filter(is_active=True).order_by('-created_at')[:5]
        recent_leaves = LeaveApplication.objects.filter(status='pending').order_by('-applied_date')[:5]
        recent_employees = Employee.objects.filter(is_active=True).order_by('-created_at')[:5]
        
        context['recent_projects'] = recent_projects
        context['recent_leaves'] = recent_leaves
        context['recent_employees'] = recent_employees
        
        return render(request, 'dashboards/super_admin_dashboard.html', context)
    
    # ==================== ADMIN DASHBOARD ====================
    elif role == 'admin':
        # 🔥 Admin is now in Employee table, so we fetch as employee
        employee = Employee.objects.get(id=user_id)
        
        # Admin Stats (exclude other admins from team count)
        context['team_members'] = Employee.objects.filter(is_active=True).exclude(role='admin').count()
        context['active_projects'] = Project.objects.filter(is_active=True, status='in_progress').count()
        context['interested_clients'] = Client.objects.filter(status='interested', is_active=True).count()
        context['daily_reports_today'] = DailyWorkReport.objects.filter(work_date=today, is_active=True).count()
        
        # Team performance for last 6 months
        team_performance = []
        for i in range(5, -1, -1):
            month = current_month - i
            year = current_year
            if month <= 0:
                month += 12
                year -= 1
            
            start_date = date(year, month, 1)
            end_date = date(year, month, calendar.monthrange(year, month)[1])
            
            dev_reports = DailyWorkReport.objects.filter(
                employee__role='developer',
                work_date__range=[start_date, end_date],
                is_active=True
            ).count()
            
            seo_reports = DailyWorkReport.objects.filter(
                employee__role='seos',
                work_date__range=[start_date, end_date],
                is_active=True
            ).count()
            
            sales_clients = Client.objects.filter(
                added_by__role='sales',
                created_at__range=[start_date, end_date]
            ).count()
            
            team_performance.append({
                'month': calendar.month_abbr[month],
                'developers': dev_reports,
                'seo': seo_reports,
                'sales': sales_clients
            })
        
        context['team_performance'] = json.dumps(team_performance)
        
        # Project progress
        projects_with_progress = []
        active_projects = Project.objects.filter(is_active=True, status='in_progress')[:6]
        for project in active_projects:
            # Calculate days remaining
            days_remaining = (project.deadline - today).days if project.deadline > today else 0
            
            # Calculate progress based on reports
            total_reports = DailyWorkReport.objects.filter(project=project, is_active=True).count()
            projects_with_progress.append({
                'project': project,
                'days_remaining': days_remaining,
                'total_reports': total_reports
            })
        
        context['projects_with_progress'] = projects_with_progress
        
        # Pending tasks
        context['pending_leaves'] = LeaveApplication.objects.filter(status='pending', is_active=True).count()
        context['unreviewed_reports'] = DailyWorkReport.objects.filter(is_reviewed=False, is_active=True).count()
        
        # 🔥 NEW: Admin's own attendance/leave stats
        start_date = date(current_year, current_month, 1)
        end_date = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
        
        context['my_attendance_days'] = Attendance.objects.filter(
            employee=employee,
            attendance_date__range=[start_date, end_date],
            status='present'
        ).count()
        
        leave_balance = EmployeeLeaveBalance.objects.filter(employee=employee).first()
        if leave_balance:
            casual_available = max(0, 1 - leave_balance.casual_leaves_taken_this_month)
            sick_available = float(leave_balance.sick_leave_balance)
            context['my_remaining_leaves'] = casual_available + sick_available
        else:
            context['my_remaining_leaves'] = 7
        
        return render(request, 'dashboards/admin_dashboard.html', context)
    
    # ==================== HR DASHBOARD ====================
    elif role == 'hr':
        employee = Employee.objects.get(id=user_id)
        
        # HR Stats
        context['pending_leaves'] = LeaveApplication.objects.filter(status='pending', is_active=True).count()
        
        # Today's attendance (including admins)
        today_attendance = Attendance.objects.filter(attendance_date=today)
        total_employees = Employee.objects.filter(is_active=True).count()
        present_today = today_attendance.filter(status='present').count()
        context['present_today'] = present_today
        context['total_employees'] = total_employees
        context['attendance_percentage'] = round((present_today / total_employees * 100), 1) if total_employees > 0 else 0
        
        # Salary processing
        context['salary_processing'] = Employee.objects.filter(is_active=True).count()
        
        # Monthly attendance rate
        start_date = date(current_year, current_month, 1)
        end_date = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
        
        month_attendance = Attendance.objects.filter(attendance_date__range=[start_date, end_date])
        total_present = month_attendance.filter(status='present').count()
        total_records = month_attendance.count()
        context['attendance_rate'] = round((total_present / total_records * 100), 1) if total_records > 0 else 0
        
        # Leave distribution
        all_leaves = LeaveApplication.objects.filter(is_active=True)
        context['approved_leaves'] = all_leaves.filter(status='approved').count()
        context['pending_leaves_count'] = all_leaves.filter(status='pending').count()
        context['rejected_leaves'] = all_leaves.filter(status='rejected').count()
        
        # Monthly attendance trend (last 6 months)
        attendance_trend = []
        for i in range(5, -1, -1):
            month = current_month - i
            year = current_year
            if month <= 0:
                month += 12
                year -= 1
            
            start_date = date(year, month, 1)
            end_date = date(year, month, calendar.monthrange(year, month)[1])
            
            month_att = Attendance.objects.filter(attendance_date__range=[start_date, end_date])
            attendance_trend.append({
                'month': calendar.month_abbr[month],
                'present': month_att.filter(status='present').count(),
                'absent': month_att.filter(status='absent').count(),
                'halfDay': month_att.filter(status='half_day').count()
            })
        
        context['attendance_trend'] = json.dumps(attendance_trend)
        
        # Department wise attendance (including admin)
        dept_attendance = []
        for dept_role, dept_name in [('admin', 'Admin'), ('developer', 'Developer'), ('seos', 'SEO'), ('sales', 'Sales'), ('hr', 'HR')]:
            dept_employees = Employee.objects.filter(role=dept_role, is_active=True)
            dept_emp_count = dept_employees.count()
            
            if dept_emp_count > 0:
                dept_present = Attendance.objects.filter(
                    employee__in=dept_employees,
                    attendance_date__range=[start_date, end_date],
                    status='present'
                ).count()
                
                total_working_days = calendar.monthrange(current_year, current_month)[1]
                rate = round((dept_present / (dept_emp_count * total_working_days) * 100), 1)
            else:
                rate = 0
            
            dept_attendance.append({
                'dept': dept_name,
                'rate': rate
            })
        
        context['dept_attendance'] = json.dumps(dept_attendance)
        
        # 🔥 HR's own stats
        context['my_attendance_days'] = Attendance.objects.filter(
            employee=employee,
            attendance_date__range=[start_date, end_date],
            status='present'
        ).count()
        
        leave_balance = EmployeeLeaveBalance.objects.filter(employee=employee).first()
        if leave_balance:
            casual_available = max(0, 1 - leave_balance.casual_leaves_taken_this_month)
            sick_available = float(leave_balance.sick_leave_balance)
            context['my_remaining_leaves'] = casual_available + sick_available
        else:
            context['my_remaining_leaves'] = 7
        
        return render(request, 'dashboards/hr_dashboard.html', context)
    
    # ==================== DEVELOPER DASHBOARD ====================
    elif role == 'developer':
        employee = Employee.objects.get(id=user_id)
        
        # Developer Stats
        context['assigned_projects'] = ProjectAssignment.objects.filter(
            employee=employee,
            is_active=True
        ).count()
        
        context['reports_submitted'] = DailyWorkReport.objects.filter(
            employee=employee,
            work_date__month=current_month,
            work_date__year=current_year,
            is_active=True
        ).count()
        
        # Remaining leaves
        leave_balance = EmployeeLeaveBalance.objects.filter(employee=employee).first()
        if leave_balance:
            casual_available = max(0, 1 - leave_balance.casual_leaves_taken_this_month)
            sick_available = float(leave_balance.sick_leave_balance)
            context['remaining_leaves'] = casual_available + sick_available
        else:
            context['remaining_leaves'] = 7
        
        # Work hours this month
        start_date = date(current_year, current_month, 1)
        end_date = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
        
        month_attendance = Attendance.objects.filter(
            employee=employee,
            attendance_date__range=[start_date, end_date]
        ).aggregate(total_hours=Sum('total_work_hours'))
        
        context['work_hours'] = int(month_attendance['total_hours'] or 0)
        
        # Attendance this month
        context['attendance_days'] = Attendance.objects.filter(
            employee=employee,
            attendance_date__range=[start_date, end_date],
            status='present'
        ).count()
        
        # Project timeline
        assigned_projects = ProjectAssignment.objects.filter(
            employee=employee,
            is_active=True
        ).select_related('project')[:5]
        
        project_timeline = []
        for assignment in assigned_projects:
            project = assignment.project
            days_remaining = (project.deadline - today).days if project.deadline > today else 0
            
            # Calculate hours from reports
            project_reports = DailyWorkReport.objects.filter(
                project=project,
                employee=employee,
                is_active=True
            ).aggregate(total_hours=Sum('hours_worked'))
            
            project_timeline.append({
                'project': project,
                'days_remaining': days_remaining,
                'hours_spent': float(project_reports['total_hours'] or 0)
            })
        
        context['project_timeline'] = project_timeline
        
        # Weekly work hours (last 7 days)
        weekly_hours = []
        for i in range(6, -1, -1):
            check_date = today - timedelta(days=i)
            att = Attendance.objects.filter(employee=employee, attendance_date=check_date).first()
            weekly_hours.append({
                'day': check_date.strftime('%a'),
                'hours': float(att.total_work_hours) if att else 0
            })
        
        context['weekly_hours'] = json.dumps(weekly_hours)
        
        # Task status
        all_reports = DailyWorkReport.objects.filter(employee=employee, is_active=True)
        context['completed_tasks'] = all_reports.filter(overall_status='completed').count()
        context['inprogress_tasks'] = all_reports.filter(overall_status='in_progress').count()
        context['pending_tasks'] = all_reports.filter(overall_status='pending').count()
        context['blocked_tasks'] = all_reports.filter(overall_status='blocked').count()
        
        return render(request, 'dashboards/developer_dashboard.html', context)
    
    # ==================== SALES DASHBOARD ====================
    elif role == 'sales':
        employee = Employee.objects.get(id=user_id)
        
        # Sales Stats
        context['total_clients'] = Client.objects.filter(added_by=employee, is_active=True).count()
        context['interested_clients'] = Client.objects.filter(added_by=employee, status='interested', is_active=True).count()
        
        # Calls this month
        start_date = date(current_year, current_month, 1)
        end_date = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
        
        context['calls_this_month'] = ClientCallLog.objects.filter(
            called_by=employee,
            call_date__range=[start_date, end_date]
        ).count()
        
        # Conversion rate
        total_clients = Client.objects.filter(added_by=employee).count()
        interested = Client.objects.filter(added_by=employee, status='interested').count()
        context['conversion_rate'] = round((interested / total_clients * 100), 1) if total_clients > 0 else 0
        
        # Remaining leaves
        leave_balance = EmployeeLeaveBalance.objects.filter(employee=employee).first()
        if leave_balance:
            casual_available = max(0, 1 - leave_balance.casual_leaves_taken_this_month)
            sick_available = float(leave_balance.sick_leave_balance)
            context['remaining_leaves'] = casual_available + sick_available
        else:
            context['remaining_leaves'] = 7
        
        # Attendance this month
        context['attendance_days'] = Attendance.objects.filter(
            employee=employee,
            attendance_date__range=[start_date, end_date],
            status='present'
        ).count()
        
        # Client status breakdown
        my_clients = Client.objects.filter(added_by=employee, is_active=True)
        context['interested_count'] = my_clients.filter(status='interested').count()
        context['followup_count'] = my_clients.filter(status='follow_up').count()
        context['contacted_count'] = my_clients.filter(status='contacted').count()
        context['notinterested_count'] = my_clients.filter(status='not_interested').count()
        
        # Monthly call trend (last 6 months)
        call_trend = []
        for i in range(5, -1, -1):
            month = current_month - i
            year = current_year
            if month <= 0:
                month += 12
                year -= 1
            
            start_date = date(year, month, 1)
            end_date = date(year, month, calendar.monthrange(year, month)[1])
            
            calls = ClientCallLog.objects.filter(
                called_by=employee,
                call_date__range=[start_date, end_date]
            ).count()
            
            interested = Client.objects.filter(
                added_by=employee,
                status='interested',
                updated_at__range=[start_date, end_date]
            ).count()
            
            call_trend.append({
                'month': calendar.month_abbr[month],
                'calls': calls,
                'interested': interested
            })
        
        context['call_trend'] = json.dumps(call_trend)
        
        # Upcoming follow-ups
        upcoming_followups = ClientCallLog.objects.filter(
            called_by=employee,
            next_follow_up__gte=today
        ).order_by('next_follow_up')[:5]
        
        context['upcoming_followups'] = upcoming_followups
        
        return render(request, 'dashboards/sales_dashboard.html', context)
    
    # ==================== SEO DASHBOARD ====================
    elif role == 'seos':
        employee = Employee.objects.get(id=user_id)
        
        # SEO Stats
        context['assigned_projects'] = ProjectAssignment.objects.filter(
            employee=employee,
            is_active=True
        ).count()
        
        context['reports_submitted'] = DailyWorkReport.objects.filter(
            employee=employee,
            work_date__month=current_month,
            work_date__year=current_year,
            is_active=True
        ).count()
        
        # Remaining leaves
        leave_balance = EmployeeLeaveBalance.objects.filter(employee=employee).first()
        if leave_balance:
            casual_available = max(0, 1 - leave_balance.casual_leaves_taken_this_month)
            sick_available = float(leave_balance.sick_leave_balance)
            context['remaining_leaves'] = casual_available + sick_available
        else:
            context['remaining_leaves'] = 7
        
        # Attendance this month
        start_date = date(current_year, current_month, 1)
        end_date = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
        
        context['attendance_days'] = Attendance.objects.filter(
            employee=employee,
            attendance_date__range=[start_date, end_date],
            status='present'
        ).count()
        
        # Project metrics
        assigned_projects = ProjectAssignment.objects.filter(
            employee=employee,
            is_active=True
        ).select_related('project')[:5]
        
        project_metrics = []
        for assignment in assigned_projects:
            project = assignment.project
            days_remaining = (project.deadline - today).days if project.deadline > today else 0
            
            # Calculate hours from reports
            project_reports = DailyWorkReport.objects.filter(
                project=project,
                employee=employee,
                is_active=True
            ).aggregate(total_hours=Sum('hours_worked'))
            
            project_metrics.append({
                'project': project,
                'days_remaining': days_remaining,
                'hours_spent': float(project_reports['total_hours'] or 0)
            })
        
        context['project_metrics'] = project_metrics
        
        # Task distribution
        all_reports = DailyWorkReport.objects.filter(employee=employee, is_active=True)
        context['completed_tasks'] = all_reports.filter(overall_status='completed').count()
        context['inprogress_tasks'] = all_reports.filter(overall_status='in_progress').count()
        context['pending_tasks'] = all_reports.filter(overall_status='pending').count()
        context['blocked_tasks'] = all_reports.filter(overall_status='blocked').count()
        
        return render(request, 'dashboards/seos_dashboard.html', context)
    
    # ==================== DIGITAL MARKETING DASHBOARD ====================
    elif role == 'digital_marketing':
        employee = Employee.objects.get(id=user_id)
        
        # Digital Marketing Stats
        context['assigned_projects'] = ProjectAssignment.objects.filter(
            employee=employee,
            is_active=True
        ).count()
        
        context['reports_submitted'] = DailyWorkReport.objects.filter(
            employee=employee,
            work_date__month=current_month,
            work_date__year=current_year,
            is_active=True
        ).count()
        
        # Remaining leaves
        leave_balance = EmployeeLeaveBalance.objects.filter(employee=employee).first()
        if leave_balance:
            casual_available = max(0, 1 - leave_balance.casual_leaves_taken_this_month)
            sick_available = float(leave_balance.sick_leave_balance)
            context['remaining_leaves'] = casual_available + sick_available
        else:
            context['remaining_leaves'] = 7
        
        # Attendance this month
        start_date = date(current_year, current_month, 1)
        end_date = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
        
        context['attendance_days'] = Attendance.objects.filter(
            employee=employee,
            attendance_date__range=[start_date, end_date],
            status='present'
        ).count()
        
        # Campaign metrics (similar to project metrics)
        assigned_projects = ProjectAssignment.objects.filter(
            employee=employee,
            is_active=True
        ).select_related('project')[:5]
        
        campaign_metrics = []
        for assignment in assigned_projects:
            project = assignment.project
            days_remaining = (project.deadline - today).days if project.deadline > today else 0
            
            # Calculate hours from reports
            project_reports = DailyWorkReport.objects.filter(
                project=project,
                employee=employee,
                is_active=True
            ).aggregate(total_hours=Sum('hours_worked'))
            
            campaign_metrics.append({
                'project': project,
                'days_remaining': days_remaining,
                'hours_spent': float(project_reports['total_hours'] or 0)
            })
        
        context['campaign_metrics'] = campaign_metrics
        
        # Task distribution
        all_reports = DailyWorkReport.objects.filter(employee=employee, is_active=True)
        context['completed_tasks'] = all_reports.filter(overall_status='completed').count()
        context['inprogress_tasks'] = all_reports.filter(overall_status='in_progress').count()
        context['pending_tasks'] = all_reports.filter(overall_status='pending').count()
        context['blocked_tasks'] = all_reports.filter(overall_status='blocked').count()
        
        return render(request, 'dashboards/digital_marketing_dashboard.html', context)

    else:
        return render(request, 'dashboard.html', context)


# Add this to views.py

@check_blocked_user
@login_required
def my_profile(request):
    """
    Complete user profile page - shows all details of logged-in user
    Works for both AdminUser (super_admin) and Employee (all other roles)
    """
    user_id = request.session.get('user_id')
    user_type = request.session.get('user_type')
    user_role = request.session.get('role')
    
    context = {
        'user_role': user_role,
        'user_type': user_type
    }
    
    # Get user object and related data
    if user_type == 'super_admin':
        # Super Admin from AdminUser table
        user = get_object_or_404(AdminUser, id=user_id)
        context['user'] = user
        
        # Super Admin stats
        context['total_employees'] = Employee.objects.filter(is_active=True).count()
        context['total_projects'] = Project.objects.filter(is_active=True).count()
        context['total_clients'] = Client.objects.filter(is_active=True).count()
        context['tasks_assigned'] = TaskAssignment.objects.filter(assigned_by_admin=user, is_active=True).count()
        
    else:
        # Employee (admin, hr, sales, developer, seos, digital_marketing)
        employee = get_object_or_404(Employee, id=user_id)
        context['user'] = employee
        
        # Employee documents
        context['documents'] = EmployeeDocument.objects.filter(employee=employee)
        
        # Common stats for all employees
        today = date.today()
        current_month = today.month
        current_year = today.year
        start_date = date(current_year, current_month, 1)
        end_date = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
        
        # Attendance stats
        month_attendance = Attendance.objects.filter(
            employee=employee,
            attendance_date__range=[start_date, end_date]
        )
        context['present_days'] = month_attendance.filter(status='present').count()
        context['absent_days'] = month_attendance.filter(status='absent').count()
        context['half_days'] = month_attendance.filter(status='half_day').count()
        context['leave_days'] = month_attendance.filter(status='on_leave').count()
        
        # Leave balance
        leave_balance = EmployeeLeaveBalance.objects.filter(employee=employee).first()
        if leave_balance:
            casual_available = max(0, 1 - leave_balance.casual_leaves_taken_this_month)
            sick_available = float(leave_balance.sick_leave_balance)
            context['casual_leave_available'] = casual_available
            context['sick_leave_available'] = sick_available
            context['total_leave_balance'] = casual_available + sick_available
        else:
            context['casual_leave_available'] = 1
            context['sick_leave_available'] = 6
            context['total_leave_balance'] = 7
        
        # Role-specific stats
        if user_role == 'admin':
            context['team_members'] = Employee.objects.filter(is_active=True).exclude(role='admin').count()
            context['active_projects'] = Project.objects.filter(is_active=True, status='in_progress').count()
            context['pending_tasks'] = TaskAssignment.objects.filter(assigned_by_name=employee.full_name, status='pending').count()
            
        elif user_role == 'hr':
            context['pending_leaves'] = LeaveApplication.objects.filter(status='pending', is_active=True).count()
            context['total_employees'] = Employee.objects.filter(is_active=True).count()
            
        elif user_role == 'sales':
            context['my_clients'] = Client.objects.filter(added_by=employee, is_active=True).count()
            context['interested_clients'] = Client.objects.filter(added_by=employee, status='interested', is_active=True).count()
            context['calls_this_month'] = ClientCallLog.objects.filter(
                called_by=employee,
                call_date__range=[start_date, end_date]
            ).count()
            
        elif user_role in ['developer', 'seos', 'digital_marketing']:
            context['assigned_projects'] = ProjectAssignment.objects.filter(
                employee=employee,
                is_active=True
            ).count()
            context['assigned_tasks'] = TaskAssignment.objects.filter(
                assigned_to=employee,
                is_active=True
            ).count()
            context['pending_tasks'] = TaskAssignment.objects.filter(
                assigned_to=employee,
                status='pending',
                is_active=True
            ).count()
            context['completed_tasks'] = TaskAssignment.objects.filter(
                assigned_to=employee,
                status='completed',
                is_active=True
            ).count()
            context['reports_this_month'] = DailyWorkReport.objects.filter(
                employee=employee,
                work_date__range=[start_date, end_date],
                is_active=True
            ).count()
        
        # Recent activities (for all employees)
        context['recent_tasks'] = TaskAssignment.objects.filter(
            assigned_to=employee,
            is_active=True
        ).order_by('-assigned_date')[:5]
        
        context['recent_attendance'] = Attendance.objects.filter(
            employee=employee
        ).order_by('-attendance_date')[:7]
        
        context['recent_leaves'] = LeaveApplication.objects.filter(
            employee=employee,
            is_active=True
        ).order_by('-applied_date')[:5]
        
        # Latest salary
        context['latest_salary'] = MonthlySalary.objects.filter(
            employee=employee,
            is_saved=True
        ).order_by('-year', '-month').first()
    
    return render(request, 'Profile/profile.html', context)


# ------------------ New Views  Related Funds ------------------
@check_blocked_user
@login_required
@role_required(['super_admin'])
def initialize_company_funds(request):
    """
    Super Admin: Add initial funds (only once or add more funds)
    """
    if request.method == "POST":
        amount = Decimal(request.POST.get('amount'))
        description = request.POST.get('description', 'Initial funds deposit')
        
        # Get or create CompanyFunds
        company_funds, created = CompanyFunds.objects.get_or_create(
            id=1,  # Always single record
            defaults={'total_funds': 0}
        )
        
        # Create transaction
        transaction = FundTransaction.objects.create(
            transaction_type='initial_deposit',
            amount=amount,
            is_credit=True,
            balance_after=company_funds.total_funds + amount,
            description=description,
            created_by_name=request.session.get('full_name'),
            created_by_role='super_admin'
        )
        
        # Update funds
        company_funds.total_funds += amount
        company_funds.updated_by_name = request.session.get('full_name')
        company_funds.save()
        
        messages.success(request, f"✅ ₹{amount} added to company funds!")
        return redirect('financial_dashboard')
    
    return render(request, 'Finance/initialize_funds.html')


@check_blocked_user
@login_required
@role_required(['admin', 'super_admin', 'hr'])
def pay_salary_from_funds(request, salary_id):
    """
    Mark salary as paid and deduct from company funds
    """
    salary = get_object_or_404(MonthlySalary, id=salary_id)
    
    if request.method == "POST":
        try:
            amount_to_pay = Decimal(request.POST.get('amount_to_pay'))
            payment_date = request.POST.get('payment_date')
            payment_method = request.POST.get('payment_method')
            remarks = request.POST.get('remarks')
            
            # Check if amount is valid
            if amount_to_pay > salary.remaining_balance:
                messages.error(request, 
                    f"❌ Amount exceeds remaining balance! "
                    f"Remaining: ₹{salary.remaining_balance}"
                )
                return redirect('pay_salary_from_funds', salary_id=salary_id)
            
            # Get company funds
            company_funds = CompanyFunds.objects.get(id=1)
            
            # Check if sufficient funds
            if amount_to_pay > company_funds.total_funds:
                messages.error(request, 
                    f"❌ Insufficient funds! "
                    f"Available: ₹{company_funds.total_funds}"
                )
                return redirect('pay_salary_from_funds', salary_id=salary_id)
            
            # Create fund transaction (DEBIT)
            fund_txn = FundTransaction.objects.create(
                transaction_type='salary_payment',
                amount=amount_to_pay,
                is_credit=False,  # Money OUT
                balance_after=company_funds.total_funds - amount_to_pay,
                salary=salary,
                description=f"Salary paid to {salary.employee_name} for {calendar.month_name[salary.month]} {salary.year}",
                created_by_name=request.session.get('full_name'),
                created_by_role=request.session.get('role')
            )
            
            # Update salary record
            salary.paid_amount += amount_to_pay
            salary.remaining_balance -= amount_to_pay
            salary.payment_date = payment_date
            salary.payment_from_funds = True
            salary.fund_transaction = fund_txn
            salary.save()
            
            # Update company funds
            company_funds.total_funds -= amount_to_pay
            company_funds.total_paid_as_salary += amount_to_pay
            company_funds.total_profit = (
                company_funds.total_received_from_clients - 
                company_funds.total_paid_as_salary
            )
            company_funds.save()
            
            messages.success(request, 
                f"✅ Salary payment of ₹{amount_to_pay} recorded! "
                f"Remaining: ₹{salary.remaining_balance}"
            )
            return redirect('salary_sheet')
            
        except Exception as e:
            messages.error(request, f"❌ Error: {str(e)}")
    
    company_funds = CompanyFunds.objects.get(id=1)
    
    context = {
        'salary': salary,
        'company_funds': company_funds,
        'today': date.today().isoformat()
    }
    return render(request, 'Finance/pay_salary_from_funds.html', context)


@check_blocked_user
@login_required
@role_required(['super_admin', 'admin'])
def financial_dashboard(request):
    """
    Complete financial overview with charts
    """
    try:
        company_funds = CompanyFunds.objects.get(id=1)
    except CompanyFunds.DoesNotExist:
        company_funds = None
    
    # Recent transactions (last 10)
    recent_transactions = FundTransaction.objects.all()[:10]
    
    # Project payment summary
    total_project_value = Project.objects.filter(
        is_active=True
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    total_received = Project.objects.filter(
        is_active=True
    ).aggregate(total=Sum('amount_received'))['total'] or 0
    
    total_pending = Project.objects.filter(
        is_active=True
    ).aggregate(total=Sum('amount_pending'))['total'] or 0
    
    # 🔥 FIXED: Salary payment summary from FundTransaction (not MonthlySalary)
    total_salary_paid = FundTransaction.objects.filter(
        transaction_type='salary_payment',
        is_credit=False
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Total salary payable (from MonthlySalary - this is correct)
    total_salary_payable = MonthlySalary.objects.filter(
        is_saved=True
    ).aggregate(total=Sum('net_payable'))['total'] or 0
    
    total_salary_pending = total_salary_payable - total_salary_paid
    
    # Monthly trends (last 6 months)
    monthly_data = []
    today = date.today()
    
    for i in range(5, -1, -1):
        month = today.month - i
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        
        start_date = date(year, month, 1)
        end_date = date(year, month, calendar.monthrange(year, month)[1])
        
        # Income (client payments)
        income = FundTransaction.objects.filter(
            transaction_type='client_payment',
            transaction_date__range=[start_date, end_date],
            is_credit=True
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Expense (salary payments)
        expense = FundTransaction.objects.filter(
            transaction_type='salary_payment',
            transaction_date__range=[start_date, end_date],
            is_credit=False
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        monthly_data.append({
            'month': calendar.month_abbr[month],
            'income': float(income),
            'expense': float(expense),
            'profit': float(income - expense)
        })
    
    context = {
        'company_funds': company_funds,
        'recent_transactions': recent_transactions,
        'total_project_value': total_project_value,
        'total_received': total_received,
        'total_pending': total_pending,
        'total_salary_payable': total_salary_payable,
        'total_salary_paid': total_salary_paid,
        'total_salary_pending': total_salary_pending,
        'monthly_data': json.dumps(monthly_data)
    }
    
    return render(request, 'Finance/financial_dashboard.html', context)


@check_blocked_user
@login_required
@role_required(['super_admin', 'admin'])
def all_transactions(request):
    """
    Complete transaction history with filters
    """
    transactions = FundTransaction.objects.all()
    
    # Filters
    txn_type = request.GET.get('type')
    if txn_type:
        transactions = transactions.filter(transaction_type=txn_type)
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from and date_to:
        transactions = transactions.filter(
            transaction_date__date__range=[date_from, date_to]
        )
    
    # Pagination
    paginator = Paginator(transactions, 20)
    page = request.GET.get('page')
    
    try:
        transactions = paginator.page(page)
    except PageNotAnInteger:
        transactions = paginator.page(1)
    except EmptyPage:
        transactions = paginator.page(paginator.num_pages)
    
    context = {
        'transactions': transactions
    }
    return render(request, 'Finance/all_transactions.html', context)



# ==================== COMPANY EXPENSES ====================

@check_blocked_user
@login_required
def add_expense(request):
    """
    Add company expense (auto deducts from funds)
    """
    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get('amount'))
            description = request.POST.get('description')
            payment_method = request.POST.get('payment_method')
            expense_date = request.POST.get('expense_date')
            
            # Check if sufficient funds
            company_funds = CompanyFunds.objects.get(id=1)
            
            if amount > company_funds.total_funds:
                messages.error(request, 
                    f"❌ Insufficient funds! Available: ₹{company_funds.total_funds}"
                )
                return redirect('add_expense')
            
            # Create fund transaction (DEBIT)
            fund_txn = FundTransaction.objects.create(
                transaction_type='adjustment',
                amount=amount,
                is_credit=False,  # Money OUT
                balance_after=company_funds.total_funds - amount,
                description=f"Expense: {description}",
                created_by_name=request.session.get('full_name'),
                created_by_role=request.session.get('role')
            )
            
            # Create expense record
            expense = CompanyExpense.objects.create(
                expense_date=expense_date,
                amount=amount,
                description=description,
                payment_method=payment_method,
                fund_transaction=fund_txn,
                added_by_name=request.session.get('full_name'),
                added_by_role=request.session.get('role')
            )
            
            # Update company funds
            company_funds.total_funds -= amount
            company_funds.total_profit = (
                company_funds.total_received_from_clients - 
                company_funds.total_paid_as_salary -
                amount  # Subtract all expenses
            )
            company_funds.save()
            
            messages.success(request, 
                f"✅ Expense {expense.expense_id} added! ₹{amount} deducted from funds."
            )
            return redirect('expense_list')
            
        except Exception as e:
            messages.error(request, f"❌ Error: {str(e)}")
    
    context = {
        'today': date.today().isoformat()
    }
    return render(request, 'Finance/add_expense.html', context)


@check_blocked_user
@login_required
@role_required(['super_admin', 'admin'])
def expense_list(request):
    """
    View all company expenses with filters and pagination
    """
    expenses_list = CompanyExpense.objects.all().order_by('-expense_date', '-created_at')
    
    # Date filter
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from and date_to:
        expenses_list = expenses_list.filter(
            expense_date__range=[date_from, date_to]
        )
    
    # Payment method filter
    payment_filter = request.GET.get('payment_method')
    if payment_filter:
        expenses_list = expenses_list.filter(payment_method=payment_filter)
    
    # Calculate total (of filtered results)
    total_expenses = expenses_list.aggregate(total=Sum('amount'))['total'] or 0
    
    # Pagination
    paginator = Paginator(expenses_list, 15)  # 15 expenses per page
    page = request.GET.get('page')
    
    try:
        expenses = paginator.page(page)
    except PageNotAnInteger:
        expenses = paginator.page(1)
    except EmptyPage:
        expenses = paginator.page(paginator.num_pages)
    
    context = {
        'expenses': expenses,
        'total_expenses': total_expenses
    }
    return render(request, 'Finance/expense_list.html', context)


@check_blocked_user
@login_required
@role_required(['super_admin'])
def delete_expense(request, expense_id):
    """
    Delete expense and refund to company funds
    """
    expense = get_object_or_404(CompanyExpense, id=expense_id)
    
    try:
        # Refund to company funds
        company_funds = CompanyFunds.objects.get(id=1)
        company_funds.total_funds += expense.amount
        company_funds.save()
        
        # Delete fund transaction if exists
        if expense.fund_transaction:
            expense.fund_transaction.delete()
        
        expense_id_display = expense.expense_id
        amount = expense.amount
        expense.delete()
        
        messages.success(request, 
            f"✅ Expense {expense_id_display} deleted! ₹{amount} refunded to funds."
        )
    except Exception as e:
        messages.error(request, f"❌ Error: {str(e)}")
    
    return redirect('expense_list')


# ------------------------ Employee ----------------------

# ADD EMPLOYEE (with Manual Employee ID Entry)
@check_blocked_user
@login_required
@role_required(['super_admin'])
def add_employee(request):
    """
    🔥 UPDATED: Manual joining date + auto training status check
    """
    if request.method == "POST":
        try:
            with transaction.atomic():
                # Step 1 - Basic Info
                employee_id = request.POST.get('employee_id')
                full_name = request.POST.get('full_name')
                email = request.POST.get('email')
                mobile = request.POST.get('mobile')
                dob = request.POST.get('dob')
                gender = request.POST.get('gender')
                profile_pic = request.FILES.get('profile_pic')
                username = request.POST.get('username')
                password = request.POST.get('password')

                # Step 2 - Address
                address_line = request.POST.get('address_line')
                city = request.POST.get('city')
                state = request.POST.get('state')
                pincode = request.POST.get('pincode')

                # Step 3 - Emergency Contact
                emergency_name = request.POST.get('emergency_contact_name')
                emergency_number = request.POST.get('emergency_contact_number')
                emergency_relation = request.POST.get('emergency_contact_relation')

                # Step 4 - Professional Details
                role = request.POST.get('role')
                designation = request.POST.get('designation')
                base_salary = request.POST.get('base_salary')
                resume = request.FILES.get('resume')
                
                # 🔥 IMPORTANT: Form से date को string के रूप में प्राप्त करें
                joining_date_str = request.POST.get('joining_date')
                
                # अब इसे proper date object में convert करें
                if joining_date_str:
                    # अगर date दी गई है, तो string को date में बदलें
                    joining_date = datetime.strptime(joining_date_str, '%Y-%m-%d').date()
                else:
                    # अगर date नहीं दी गई है, तो आज की date का उपयोग करें
                    joining_date = date.today()
                
                # Step 5 - Bank Details
                account_number = request.POST.get('account_number')
                ifsc_code = request.POST.get('ifsc_code')
                account_holder_name = request.POST.get('account_holder_name')
                bank_name = request.POST.get('bank_name')
                bank_address = request.POST.get('bank_address')

                # 🔥 अब आप एक proper date object पास कर रहे हैं
                emp = Employee.objects.create(
                    employee_id=employee_id,
                    full_name=full_name,
                    email=email,
                    mobile=mobile,
                    dob=dob,
                    gender=gender,
                    profile_pic=profile_pic,
                    username=username,
                    password=password,
                    address_line=address_line,
                    city=city,
                    state=state,
                    pincode=pincode,
                    emergency_contact_name=emergency_name,
                    emergency_contact_number=emergency_number,
                    emergency_contact_relation=emergency_relation,
                    role=role,
                    designation=designation,
                    base_salary=base_salary,
                    resume=resume,
                    account_number=account_number,
                    ifsc_code=ifsc_code,
                    account_holder_name=account_holder_name,
                    bank_name=bank_name,
                    bank_address=bank_address,
                    training_start_date=joining_date,  # यह अब 100% date object है
                    is_in_training=True,
                    training_per_day_salary=Decimal('100.00')
                )

                # Handle Multiple Documents
                document_names = request.POST.getlist('document_name[]')
                document_files = request.FILES.getlist('documents[]')

                for name, file in zip(document_names, document_files):
                    if name and file:
                        EmployeeDocument.objects.create(
                            employee=emp,
                            document_name=name,
                            document_file=file
                        )

                # 🔥 Check training status
                emp.check_training_status()
                
                # अब यह line error नहीं देगी क्योंकि emp.training_start_date एक वास्तविक date object है
                if emp.is_in_training:
                    messages.success(request, 
                        f"✅ Employee {emp.employee_id} added! "
                        f"Training: {emp.training_days_remaining} working days remaining (₹100/day). "
                        f"Joining Date: {emp.training_start_date.strftime('%d %b %Y')}"
                    )
                else:
                    messages.success(request, 
                        f"✅ Employee {emp.employee_id} added! Training already completed."
                    )
                
                return redirect("employee_list")

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            import traceback
            print(traceback.format_exc())  # Debug ke liye

    context = {
        'today': date.today().isoformat()
    }
    return render(request, "employee/add_employee.html", context)


# EMPLOYEE LIST
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def employee_list(request):
    employees_list = Employee.objects.all().order_by('-id')
    
    # Pagination
    paginator = Paginator(employees_list, 10)
    page = request.GET.get('page')
    
    try:
        employees = paginator.page(page)
    except PageNotAnInteger:
        employees = paginator.page(1)
    except EmptyPage:
        employees = paginator.page(paginator.num_pages)
    
    return render(request, "employee/employee_list.html", {"employees": employees})


# EDIT EMPLOYEE
@check_blocked_user
@login_required
@role_required(['super_admin'])
def edit_employee(request, id):
    """
    🔥 UPDATED: Allow editing joining date + re-check training status
    """
    emp = get_object_or_404(Employee, id=id)

    if request.method == "POST":
        # Update Basic Info
        emp.employee_id = request.POST.get('employee_id')
        emp.full_name = request.POST.get('full_name')
        emp.email = request.POST.get('email')
        emp.mobile = request.POST.get('mobile')
        emp.dob = request.POST.get('dob')
        emp.gender = request.POST.get('gender')

        if request.FILES.get('profile_pic'):
            emp.profile_pic = request.FILES.get('profile_pic')

        emp.username = request.POST.get('username')

        # Update Password only if provided
        new_password = request.POST.get('password')
        if new_password:
            emp.password = new_password

        # Update Address
        emp.address_line = request.POST.get('address_line')
        emp.city = request.POST.get('city')
        emp.state = request.POST.get('state')
        emp.pincode = request.POST.get('pincode')

        # Update Emergency Contact
        emp.emergency_contact_name = request.POST.get('emergency_contact_name')
        emp.emergency_contact_number = request.POST.get('emergency_contact_number')
        emp.emergency_contact_relation = request.POST.get('emergency_contact_relation')

        # Update Professional Details
        emp.role = request.POST.get('role')
        emp.designation = request.POST.get('designation')
        emp.base_salary = request.POST.get('base_salary')

        if request.FILES.get('resume'):
            emp.resume = request.FILES.get('resume')
        
        # Update Bank Details
        emp.account_number = request.POST.get('account_number')
        emp.ifsc_code = request.POST.get('ifsc_code')
        emp.account_holder_name = request.POST.get('account_holder_name')
        emp.bank_name = request.POST.get('bank_name')
        emp.bank_address = request.POST.get('bank_address')
        
        # 🔥 Update joining date
        new_joining_date = request.POST.get('joining_date')
        if new_joining_date:
            emp.training_start_date = new_joining_date

        emp.save()
        
        # 🔥 Re-check training status after update
        emp.check_training_status()

        # Add New Documents
        document_names = request.POST.getlist('document_name[]')
        document_files = request.FILES.getlist('documents[]')

        for name, file in zip(document_names, document_files):
            if name and file:
                EmployeeDocument.objects.create(
                    employee=emp,
                    document_name=name,
                    document_file=file
                )

        messages.success(request, f"Employee {emp.employee_id} updated successfully!")
        return redirect("employee_list")

    documents = EmployeeDocument.objects.filter(employee=emp)
    
    context = {
        "emp": emp,
        "documents": documents,
        "today": date.today().isoformat()
    }
    return render(request, "employee/edit_employee.html", context)


# DELETE EMPLOYEE
@check_blocked_user
@login_required
@role_required(['super_admin'])
def delete_employee(request, id):
    emp = get_object_or_404(Employee, id=id)
    employee_id = emp.employee_id
    emp.delete()
    messages.success(request, f"Employee {employee_id} deleted successfully!")
    return redirect("employee_list")


# DELETE EMPLOYEE DOCUMENT
@check_blocked_user
@login_required
@role_required(['super_admin'])
def delete_employee_document(request, id):
    doc = get_object_or_404(EmployeeDocument, id=id)
    employee_id = doc.employee.id
    doc.delete()
    messages.success(request, "Document deleted successfully!")
    return redirect("edit_employee", id=employee_id)


# TOGGLE EMPLOYEE STATUS
@check_blocked_user
@login_required
def toggle_employee_status(request, id):
    emp = get_object_or_404(Employee, id=id)

    if request.method == "POST":
        emp.is_active = request.POST.get('is_active') == 'on'
        emp.save()

        status = "activated" if emp.is_active else "deactivated"
        messages.success(request, f"Employee {emp.employee_id} has been {status}!")

    return redirect("edit_employee", id=id)



# TOGGLE EMPLOYEE BLOCK
@check_blocked_user
@login_required
def toggle_employee_block(request, id):
    emp = get_object_or_404(Employee, id=id)

    if request.method == "POST":
        emp.is_blocked = request.POST.get('is_blocked') == 'on'

        if emp.is_blocked:
            # Get the current user from session
            user_type = request.session.get('user_type')
            user_id = request.session.get('user_id')
            
            if user_type == 'super_admin':
                # Fetch the AdminUser instance
                blocker = AdminUser.objects.get(id=user_id)
                emp.blocked_by = blocker
            else:
                # Handle case where non-super_admin tries to block (shouldn't happen with proper permissions)
                messages.error(request, "Only Super Admin can block employees!")
                return redirect("employee_list")
            
            from django.utils import timezone
            emp.blocked_at = timezone.now()
        else:
            emp.blocked_by = None
            emp.blocked_at = None

        emp.save()

        status = "blocked" if emp.is_blocked else "unblocked"
        messages.success(request, f"Employee {emp.employee_id} has been {status}!")

    # Changed from redirecting to edit page to redirecting to employee list
    return redirect("employee_list")



# EMAIL CHECK
def check_email_unique(request):
    email = request.GET.get('email', '')
    employee_id = request.GET.get('employee_id', None)

    if employee_id:
        is_unique = not Employee.objects.filter(email=email).exclude(id=employee_id).exists()
    else:
        is_unique = not Employee.objects.filter(email=email).exists()

    return JsonResponse({'is_unique': is_unique})


# USERNAME CHECK
def check_username_unique(request):
    username = request.GET.get('username', '')
    employee_id = request.GET.get('employee_id', None)

    if employee_id:
        is_unique = not Employee.objects.filter(username=username).exclude(id=employee_id).exists()
    else:
        is_unique = not Employee.objects.filter(username=username).exists()

    return JsonResponse({'is_unique': is_unique})


# 🔥 NEW: EMPLOYEE ID CHECK
def check_employee_id_unique(request):
    emp_id = request.GET.get('employee_id', '')
    employee_pk = request.GET.get('employee_pk', None)

    if employee_pk:
        is_unique = not Employee.objects.filter(employee_id=emp_id).exclude(id=employee_pk).exists()
    else:
        is_unique = not Employee.objects.filter(employee_id=emp_id).exists()

    return JsonResponse({'is_unique': is_unique})




# =-=-=-=-=-=-=-=-=-=-=-=-=-=-= Task Assignment =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# ------------------- SUPER ADMIN VIEWS -------------------

@check_blocked_user
@login_required
@role_required(['super_admin'])
def assign_task(request):
    """
    Super Admin: Assign task to employee
    """
    if request.method == "POST":
        try:
            employee_id = request.POST.get('employee_id')
            employee = get_object_or_404(Employee, id=employee_id)
            
            task_title = request.POST.get('task_title')
            task_description = request.POST.get('task_description')
            task_file = request.FILES.get('task_file')
            due_date = request.POST.get('due_date')
            due_time = request.POST.get('due_time')
            priority = request.POST.get('priority')
            
            # Get super admin info
            user_id = request.session.get('user_id')
            user_name = request.session.get('full_name')
            admin_user = AdminUser.objects.get(id=user_id)
            
            # Create task
            task = TaskAssignment.objects.create(
                assigned_to=employee,
                assigned_to_id_display=employee.employee_id,
                assigned_to_name=employee.full_name,
                assigned_to_role=employee.role,
                task_title=task_title,
                task_description=task_description,
                task_file=task_file,
                due_date=due_date,
                due_time=due_time,
                priority=priority,
                assigned_by_admin=admin_user,
                assigned_by_name=user_name,
                assigned_by_role='super_admin',
                status='pending'
            )
            
            messages.success(request, f"✅ Task {task.task_id} assigned to {employee.full_name} successfully!")
            return redirect('admin_task_list')
            
        except Exception as e:
            messages.error(request, f"❌ Error: {str(e)}")
            return redirect('assign_task')
    
    # GET request - show form
    context = {
        'today': date.today().isoformat(),
        'current_time': datetime.now().strftime('%H:%M')
    }
    return render(request, 'Tasks/assign_task.html', context)


@check_blocked_user
@login_required
@role_required(['super_admin'])
def get_employees_by_role_ajax(request):
    """
    AJAX: Get employees by role for task assignment
    """
    try:
        role = request.GET.get('role', '').strip()
        
        if not role:
            return JsonResponse({'success': False, 'employees': []})
        
        employees = Employee.objects.filter(role=role, is_active=True).order_by('full_name')
        
        data = []
        for emp in employees:
            data.append({
                'id': emp.id,
                'employee_id': emp.employee_id,
                'full_name': emp.full_name,
                'designation': emp.designation,
                'email': emp.email
            })
        
        return JsonResponse({
            'success': True,
            'employees': data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'employees': []
        })


@check_blocked_user
@login_required
@role_required(['super_admin'])
def admin_task_list(request):
    """
    Super Admin: View all assigned tasks with filters
    """
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    employee_filter = request.GET.get('employee', '')
    priority_filter = request.GET.get('priority', '')
    
    # Base queryset
    tasks = TaskAssignment.objects.filter(is_active=True).select_related('assigned_to')
    
    # Apply filters
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if employee_filter:
        tasks = tasks.filter(assigned_to_id=employee_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    
    tasks = tasks.order_by('-assigned_date')
    
    # Get all employees for filter dropdown
    employees = Employee.objects.filter(is_active=True).order_by('full_name')
    
    # Statistics
    total_tasks = TaskAssignment.objects.filter(is_active=True).count()
    pending_tasks = TaskAssignment.objects.filter(status='pending', is_active=True).count()
    accepted_tasks = TaskAssignment.objects.filter(status='accepted', is_active=True).count()
    completed_tasks = TaskAssignment.objects.filter(status='completed', is_active=True).count()
    
    context = {
        'tasks': tasks,
        'employees': employees,
        'total_tasks': total_tasks,
        'pending_tasks': pending_tasks,
        'accepted_tasks': accepted_tasks,
        'completed_tasks': completed_tasks,
        'status_filter': status_filter,
        'employee_filter': employee_filter,
        'priority_filter': priority_filter
    }
    return render(request, 'Tasks/admin_task_list.html', context)


@check_blocked_user
@login_required
@role_required(['super_admin'])
def admin_view_task_detail(request, task_id):
    """
    Super Admin: View detailed task info
    """
    task = get_object_or_404(TaskAssignment, id=task_id, is_active=True)
    completion_files = TaskCompletionFile.objects.filter(task=task)
    
    context = {
        'task': task,
        'completion_files': completion_files
    }
    return render(request, 'Tasks/admin_task_detail.html', context)


@check_blocked_user
@login_required
@role_required(['super_admin'])
def delete_task(request, task_id):
    """
    Super Admin: Delete task (only if not accepted yet)
    """
    task = get_object_or_404(TaskAssignment, id=task_id)
    
    if task.status != 'pending':
        messages.error(request, "❌ Cannot delete task that has been accepted!")
        return redirect('admin_task_list')
    
    task_title = task.task_title
    task.is_active = False
    task.save()
    
    messages.success(request, f"✅ Task '{task_title}' deleted successfully!")
    return redirect('admin_task_list')


# ------------------- EMPLOYEE VIEWS -------------------

@check_blocked_user
@login_required
@role_required(['admin', 'hr', 'sales', 'developer', 'seos','digital_marketing'])
def my_assigned_tasks(request):
    """
    Employee: View all tasks assigned to them
    """
    user_id = request.session.get('user_id')
    employee = get_object_or_404(Employee, id=user_id)
    
    # Get filter
    status_filter = request.GET.get('status', '')
    
    # Base queryset
    tasks = TaskAssignment.objects.filter(
        assigned_to=employee,
        is_active=True
    )
    
    # Apply filter
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    tasks = tasks.order_by('-assigned_date')
    
    # Add hours and minutes calculation to each task
    for task in tasks:
        if task.time_taken_minutes:
            task.hours = task.time_taken_minutes // 60
            task.minutes = task.time_taken_minutes % 60
        else:
            task.hours = 0
            task.minutes = 0
    
    # Statistics
    pending_count = TaskAssignment.objects.filter(
        assigned_to=employee, 
        status='pending', 
        is_active=True
    ).count()
    
    accepted_count = TaskAssignment.objects.filter(
        assigned_to=employee, 
        status='accepted', 
        is_active=True
    ).count()
    
    completed_count = TaskAssignment.objects.filter(
        assigned_to=employee, 
        status='completed', 
        is_active=True
    ).count()
    
    context = {
        'tasks': tasks,
        'employee': employee,
        'pending_count': pending_count,
        'accepted_count': accepted_count,
        'completed_count': completed_count,
        'status_filter': status_filter
    }
    return render(request, 'Tasks/my_assigned_tasks.html', context)


@check_blocked_user
@login_required
@role_required(['admin', 'hr', 'sales', 'developer', 'seos','digital_marketing'])
def view_task_detail(request, task_id):
    """
    Employee: View task detail
    """
    user_id = request.session.get('user_id')
    task = get_object_or_404(
        TaskAssignment, 
        id=task_id, 
        assigned_to_id=user_id,
        is_active=True
    )
    
    completion_files = TaskCompletionFile.objects.filter(task=task)
    
    context = {
        'task': task,
        'completion_files': completion_files
    }
    return render(request, 'Tasks/view_task_detail.html', context)


@check_blocked_user
@login_required
@role_required(['admin', 'hr', 'sales', 'developer', 'seos','digital_marketing'])
def accept_task(request, task_id):
    """
    Employee: Accept task (timer starts)
    """
    if request.method == "POST":
        user_id = request.session.get('user_id')
        task = get_object_or_404(
            TaskAssignment, 
            id=task_id, 
            assigned_to_id=user_id,
            status='pending',
            is_active=True
        )
        
        task.status = 'accepted'
        task.accepted_date = timezone.now()
        task.save()
        
        messages.success(request, f"✅ Task '{task.task_title}' accepted! Timer started.")
        return redirect('view_task_detail', task_id=task_id)
    
    return redirect('my_assigned_tasks')


@check_blocked_user
@login_required
@role_required(['admin', 'hr', 'sales', 'developer', 'seos','digital_marketing'])
def complete_task(request, task_id):
    """
    Employee: Complete task with notes and files
    """
    user_id = request.session.get('user_id')
    task = get_object_or_404(
        TaskAssignment, 
        id=task_id, 
        assigned_to_id=user_id,
        status='accepted',
        is_active=True
    )
    
    if request.method == "POST":
        try:
            completion_notes = request.POST.get('completion_notes')
            
            if not completion_notes or len(completion_notes.strip()) < 10:
                messages.error(request, "❌ Please provide detailed completion notes (minimum 10 characters)!")
                return redirect('complete_task', task_id=task_id)
            
            # Update task
            task.status = 'completed'
            task.completed_date = timezone.now()
            task.completion_notes = completion_notes
            task.save()  # This will auto-calculate time_taken_minutes
            
            # Handle multiple file uploads
            completion_files = request.FILES.getlist('completion_files')
            for file in completion_files:
                TaskCompletionFile.objects.create(
                    task=task,
                    file=file,
                    file_name=file.name
                )
            
            messages.success(request, f"✅ Task '{task.task_title}' completed successfully! Time taken: {task.time_taken_minutes} minutes")
            return redirect('my_assigned_tasks')
            
        except Exception as e:
            messages.error(request, f"❌ Error: {str(e)}")
            return redirect('complete_task', task_id=task_id)
    
    # GET request - show form
    context = {'task': task}
    return render(request, 'Tasks/complete_task.html', context)


# ------------------- AJAX VIEWS -------------------

@check_blocked_user
@login_required
@role_required(['admin', 'hr', 'sales', 'developer', 'seos','digital_marketing'])
def get_task_timer(request, task_id):
    """
    AJAX: Get live timer for accepted task
    """
    try:
        user_id = request.session.get('user_id')
        task = TaskAssignment.objects.get(
            id=task_id,
            assigned_to_id=user_id,
            status='accepted'
        )
        
        if task.accepted_date:
            time_elapsed = timezone.now() - task.accepted_date
            minutes = int(time_elapsed.total_seconds() / 60)
            hours = minutes // 60
            mins = minutes % 60
            
            return JsonResponse({
                'success': True,
                'hours': hours,
                'minutes': mins,
                'total_minutes': minutes
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Task not accepted yet'
            })
            
    except TaskAssignment.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Task not found'
        })





# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= SALES (TEAM) =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=



# ADD CLIENT (With First Call Log)
@check_blocked_user
@login_required
@role_required(['sales', 'admin', 'super_admin'])
def add_client(request):
    if request.method == "POST":
        try:
            # Client Details
            company_name = request.POST.get('company_name')
            contact_person = request.POST.get('contact_person')
            email = request.POST.get('email')
            mobile = request.POST.get('mobile')
            address = request.POST.get('address')
            
            # Call Details (First Call)
            call_date = request.POST.get('call_date')
            call_time = request.POST.get('call_time')
            duration = request.POST.get('duration')
            notes = request.POST.get('notes')
            next_follow_up = request.POST.get('next_follow_up')
            client_status = request.POST.get('client_status')
            
            # Get current logged-in user info from session
            user_id = request.session.get('user_id')
            user_role = request.session.get('role')
            
            # Fetch employee object and get the name
            employee = None
            user_name = "Unknown"  # Default fallback
            
            if user_role in ['hr', 'sales', 'developer', 'seos', 'digital_marketing']:
                employee = Employee.objects.get(id=user_id)
                user_name = employee.full_name  # ✅ GET NAME FROM EMPLOYEE MODEL
            elif user_role == 'admin':
                # If admin, try to get from AdminUser or use session
                user_name = request.session.get('name', 'Admin')
            elif user_role == 'super_admin':
                user_name = request.session.get('name', 'Super Admin')
            
            # Create Client
            client = Client.objects.create(
                company_name=company_name,
                contact_person=contact_person,
                email=email,
                mobile=mobile,
                address=address,
                added_by=employee,
                added_by_name=user_name,  # ✅ NOW IT HAS THE CORRECT NAME
                added_by_role=user_role,
                status=client_status,
                total_calls=1,
                last_call_date=call_date
            )
            
            # Create First Call Log
            ClientCallLog.objects.create(
                client=client,
                called_by=employee,
                called_by_name=user_name,  # ✅ NOW IT HAS THE CORRECT NAME
                called_by_role=user_role,
                call_date=call_date,
                call_time=call_time,
                duration=duration,
                notes=notes,
                next_follow_up=next_follow_up if next_follow_up else None
            )
            
            messages.success(request, f"Client {client.client_id} added successfully with first call log!")
            return redirect("client_list")
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    context = {
        "today": date.today().isoformat()
    }
    return render(request, "sales/add_client.html", context)


# ADD CALL LOG (For Existing Clients OR New Clients)
@check_blocked_user
@login_required
@role_required(['sales', 'admin', 'super_admin'])
def add_call_log(request, client_id=None):
    client = None
    if client_id:
        client = get_object_or_404(Client, id=client_id)
    
    if request.method == "POST":
        client_type = request.POST.get('client_type')
        
        # Get current logged-in user info from session
        user_id = request.session.get('user_id')
        user_role = request.session.get('role')
        user_name = request.session.get('user_name')
        
        # Fetch employee object only if role is employee-based
        employee = None
        if user_role in ['hr', 'sales', 'developer', 'seos']:
            employee = Employee.objects.get(id=user_id)
        
        # Get call details first (needed for both new and existing clients)
        call_date = request.POST.get('call_date')
        call_time = request.POST.get('call_time')
        duration = request.POST.get('duration')
        notes = request.POST.get('notes')
        next_follow_up = request.POST.get('next_follow_up')
        client_status = request.POST.get('client_status')
        
        # Handle New Client Creation
        if client_type == 'new':
            company_name = request.POST.get('new_company_name')
            contact_person = request.POST.get('new_contact_person')
            email = request.POST.get('new_email')
            mobile = request.POST.get('new_mobile')
            address = request.POST.get('new_address')
            
            # Create new client (total_calls will be 1, no need to increment later)
            client = Client.objects.create(
                company_name=company_name,
                contact_person=contact_person,
                email=email,
                mobile=mobile,
                address=address,
                added_by=employee,
                added_by_name=user_name,
                added_by_role=user_role,
                status=client_status,  # ✅ Use the status from form
                total_calls=1,  # ✅ First call
                last_call_date=call_date
            )
        else:
            # Use existing client
            client_id = request.POST.get('existing_client_id')
            client = get_object_or_404(Client, id=client_id)
            
            # ✅ Update existing client (increment calls)
            client.status = client_status
            client.total_calls += 1
            client.last_call_date = call_date
            client.save()
        
        # Create Call Log (for both new and existing clients)
        ClientCallLog.objects.create(
            client=client,
            called_by=employee,
            called_by_name=user_name or "Unknown",  # ✅ Fallback value
            called_by_role=user_role or "Unknown",  # ✅ Fallback value
            call_date=call_date,
            call_time=call_time,
            duration=duration,
            notes=notes,
            next_follow_up=next_follow_up if next_follow_up else None
        )
        
        messages.success(request, f"Call log added successfully! Client status: {client.get_status_display()}")
        return redirect("client_list")
    
    # Get all clients for dropdown
    user_role = request.session.get('role')
    if user_role == 'sales':
        user_id = request.session.get('user_id')
        clients = Client.objects.filter(added_by_id=user_id).order_by('-id')
    else:
        clients = Client.objects.all().order_by('-id')
    
    context = {
        "client": client,
        "clients": clients,
        "today": date.today().isoformat()
    }
    return render(request, "sales/add_call_log.html", context)


# CLIENT LIST
@check_blocked_user
@login_required
@role_required(['sales', 'admin', 'super_admin'])
def client_list(request):
    user_role = request.session.get('role')
    
    if user_role == 'sales':
        user_id = request.session.get('user_id')
        clients_list = Client.objects.filter(added_by_id=user_id).order_by('-id')
    else:
        clients_list = Client.objects.all().order_by('-id')
    
    # Pagination
    paginator = Paginator(clients_list, 10)  # Show 10 clients per page
    page = request.GET.get('page')
    
    try:
        clients = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        clients = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        clients = paginator.page(paginator.num_pages)
    
    return render(request, "sales/client_list.html", {"clients": clients})


# INTERESTED CLIENTS LIST
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def interested_clients(request):
    clients = Client.objects.filter(status='interested', is_active=True).order_by('-updated_at')
    return render(request, "sales/interested_clients.html", {"clients": clients})


# EDIT CLIENT
@check_blocked_user
@login_required
@role_required(['sales', 'admin', 'super_admin'])
def edit_client(request, id):
    client = get_object_or_404(Client, id=id)
    
    user_role = request.session.get('role')
    if user_role == 'sales':
        user_id = request.session.get('user_id')
        if client.added_by_id != user_id:
            messages.error(request, "You can only edit your own clients!")
            return redirect("client_list")
    
    if request.method == "POST":
        client.company_name = request.POST.get('company_name')
        client.contact_person = request.POST.get('contact_person')
        client.email = request.POST.get('email')
        client.mobile = request.POST.get('mobile')
        client.address = request.POST.get('address')
        client.status = request.POST.get('status')
        client.save()
        
        messages.success(request, f"Client {client.client_id} updated successfully!")
        return redirect("client_list")
    
    call_logs = ClientCallLog.objects.filter(client=client)
    return render(request, "sales/edit_client.html", {
        "client": client,
        "call_logs": call_logs
    })


# DELETE CLIENT
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def delete_client(request, id):
    client = get_object_or_404(Client, id=id)
    client_id = client.client_id
    client.delete()
    messages.success(request, f"Client {client_id} deleted successfully!")
    return redirect("client_list")



# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- Projects Assigned =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# CREATE PROJECT (From Interested Client)
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def create_project(request, client_id):
    client = get_object_or_404(Client, id=client_id, status='interested')
    
    if request.method == "POST":
        try:
            user_name = request.session.get('full_name')
            user_role = request.session.get('role')
            
            # Handle file uploads
            agreement = request.FILES.get('agreement')
            module_file = request.FILES.get('module_file')
            
            # 🔥 NEW: Get total_amount
            total_amount = request.POST.get('total_amount')
            if not total_amount or Decimal(total_amount) <= 0:
                messages.error(request, "Please enter a valid project amount!")
                return redirect('create_project', client_id=client_id)
            
            project = Project.objects.create(
                project_name=request.POST.get('project_name'),
                project_type=request.POST.get('project_type'),
                client=client,
                description=request.POST.get('description'),
                start_date=request.POST.get('start_date'),
                deadline=request.POST.get('deadline'),
                budget=request.POST.get('budget') or None,
                agreement=agreement,
                module_file=module_file,
                created_by_name=user_name,
                created_by_role=user_role,
                # 🔥 NEW FIELDS
                total_amount=total_amount,
                amount_received=0,
                amount_pending=total_amount,
                payment_status='unpaid'
            )
            
            messages.success(request, 
                f"✅ Project {project.project_id} created! "
                f"Total Amount: ₹{total_amount}"
            )
            return redirect('project_list')
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    context = {
        'client': client,
        'today': date.today().isoformat()
    }
    return render(request, 'projects/create_project.html', context)


# PROJECT LIST
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin', 'developer', 'seos','digital_marketing'])
def project_list(request):
    user_role = request.session.get('role')
    
    if user_role in ['admin', 'super_admin']:
        projects_list = Project.objects.filter(is_active=True).order_by('-id')
    else:
        # Employees see only their assigned projects
        user_id = request.session.get('user_id')
        projects_list = Project.objects.filter(
            assignments__employee_id=user_id,
            is_active=True
        ).distinct().order_by('-id')
    
    # Pagination
    paginator = Paginator(projects_list, 10)  # Show 10 projects per page
    page = request.GET.get('page')
    
    try:
        projects = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        projects = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        projects = paginator.page(paginator.num_pages)
    
    context = {'projects': projects}
    return render(request, 'projects/project_list.html', context)


# PROJECT DETAIL VIEW
@check_blocked_user
@login_required
def project_detail(request, id):
    project = get_object_or_404(Project, id=id)
    assignments = ProjectAssignment.objects.filter(project=project, is_active=True)
    
    user_role = request.session.get('role')
    user_id = request.session.get('user_id')
    
    # Check if employee has access to this project
    if user_role in ['developer', 'seos']:
        # Check if they're assigned to this project
        is_assigned = ProjectAssignment.objects.filter(
            project=project,
            employee_id=user_id,
            is_active=True
        ).exists()
        
        if not is_assigned:
            messages.error(request, "You don't have access to this project!")
            return redirect('project_list')
    
    # Determine what data to show based on role
    show_sensitive_data = user_role in ['admin', 'super_admin']
    
    context = {
        'project': project,
        'assignments': assignments,
        'show_sensitive_data': show_sensitive_data
    }
    return render(request, 'projects/project_detail.html', context)



# EDIT PROJECT
@check_blocked_user
@login_required
@role_required(['super_admin'])
def edit_project(request, id):
    project = get_object_or_404(Project, id=id)
    
    if request.method == "POST":
        try:
            # 🔥 NEW: Check if total_amount can be changed
            new_total = Decimal(request.POST.get('total_amount'))
            if project.amount_received > 0 and new_total != project.total_amount:
                messages.error(request, 
                    "❌ Cannot change project amount after payments received!"
                )
                return redirect('edit_project', id=id)
            
            # Update project details
            project.project_name = request.POST.get('project_name')
            project.project_type = request.POST.get('project_type')
            project.description = request.POST.get('description')
            project.start_date = request.POST.get('start_date')
            project.deadline = request.POST.get('deadline')
            project.status = request.POST.get('status')
            
            # Update budget if provided
            budget = request.POST.get('budget')
            project.budget = budget if budget else None
            
            # 🔥 NEW: Update total_amount
            project.total_amount = new_total
            project.amount_pending = new_total - project.amount_received
            
            # Update files if new ones uploaded
            if request.FILES.get('agreement'):
                project.agreement = request.FILES.get('agreement')
            
            if request.FILES.get('module_file'):
                project.module_file = request.FILES.get('module_file')
            
            project.save()
            
            # 🔥 NEW: Recalculate payment status
            project.update_payment_status()
            
            messages.success(request, f"✅ Project {project.project_id} updated!")
            return redirect('project_detail', id=id)
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    context = {
        'project': project,
        'today': date.today().isoformat()
    }
    return render(request, 'projects/edit_project.html', context)


# DELETE PROJECT
@check_blocked_user
@login_required
@role_required(['super_admin'])
def delete_project(request, id):
    project = get_object_or_404(Project, id=id)
    project_id = project.project_id
    project_name = project.project_name
    
    # Soft delete - just mark as inactive
    project.is_active = False
    project.save()
    
    messages.success(request, f"Project {project_id} - {project_name} deleted successfully!")
    return redirect('project_list')


# UPDATE PROJECT STATUS (Admin can update status without editing entire project)
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def update_project_status(request, id):
    if request.method == "POST":
        project = get_object_or_404(Project, id=id)
        new_status = request.POST.get('status')
        
        project.status = new_status
        project.save()
        
        messages.success(request, f"Project status updated to {project.get_status_display()}!")
        return redirect('project_detail', id=id)
    
    return redirect('project_list')


# ASSIGN PROJECT TO EMPLOYEE
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def assign_project(request):
    if request.method == "POST":
        try:
            project_id = request.POST.get('project_id')
            employee_id = request.POST.get('employee_id')
            notes = request.POST.get('notes')
            
            project = get_object_or_404(Project, id=project_id)
            employee = get_object_or_404(Employee, id=employee_id)
            
            user_name = request.session.get('full_name')
            user_role = request.session.get('role')
            
            # Check if already assigned
            existing = ProjectAssignment.objects.filter(
                project=project, 
                employee=employee,
                is_active=True
            ).first()
            
            if existing:
                messages.warning(request, f"{employee.full_name} is already assigned to this project!")
                return redirect('assign_project')
            
            ProjectAssignment.objects.create(
                project=project,
                employee=employee,
                employees_id=employee.employee_id,
                employee_name=employee.full_name,
                employee_role=employee.role,
                employee_designation=employee.designation,
                assigned_by_name=user_name,
                assigned_by_role=user_role,
                notes=notes
            )
            
            messages.success(request, f"Project assigned to {employee.full_name} successfully!")
            return redirect('project_detail', id=project_id)
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('assign_project')
    
    # GET request - show form
    projects = Project.objects.filter(is_active=True).order_by('-id')
    
    context = {'projects': projects}
    return render(request, 'projects/assign_project.html', context)


# AJAX: Get employees by project type
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def get_employees_by_role(request):
    try:
        project_type = request.GET.get('project_type', '').strip()
        
        # print(f"DEBUG: Received project_type = '{project_type}'")  # Debug log
        
        employees = []
        
        # Map project type to employee role
        if project_type == 'seo':
            employees = Employee.objects.filter(role='seos', is_active=True)
            # print(f"DEBUG: Found {employees.count()} SEO employees")  # Debug log
        elif project_type == 'development':
            employees = Employee.objects.filter(role='developer', is_active=True)
            # print(f"DEBUG: Found {employees.count()} Developer employees")  # Debug log
        # else:
            # print(f"DEBUG: Invalid project_type received")  # Debug log
        
        # Prepare data
        data = []
        for emp in employees:
            data.append({
                'id': emp.id,
                'employee_id': emp.employee_id,
                'full_name': emp.full_name,
                'role': emp.role,
                'designation': emp.designation
            })
        
        # print(f"DEBUG: Returning {len(data)} employees")  # Debug log
        
        return JsonResponse({
            'success': True,
            'employees': data,
            'count': len(data)
        })
        
    except Exception as e:
        print(f"ERROR in get_employees_by_role: {str(e)}")  # Debug log
        return JsonResponse({
            'success': False,
            'error': str(e),
            'employees': []
        }, status=500)


# DELETE PROJECT ASSIGNMENT
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def remove_project_assignment(request, assignment_id):
    assignment = get_object_or_404(ProjectAssignment, id=assignment_id)
    project_id = assignment.project.id
    employee_name = assignment.employee_name
    
    assignment.is_active = False
    assignment.save()
    
    messages.success(request, f"{employee_name} removed from project!")
    return redirect('project_detail', id=project_id)


@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def record_client_payment(request, project_id):
    """
    Record payment received from client for a project
    """
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get('amount'))
            payment_date = request.POST.get('payment_date')
            payment_method = request.POST.get('payment_method')
            payment_reference = request.POST.get('payment_reference')
            remarks = request.POST.get('remarks')
            payment_proof = request.FILES.get('payment_proof')
            
            # Check if amount exceeds pending
            if amount > project.amount_pending:
                messages.error(request, 
                    f"❌ Amount exceeds pending amount! Pending: ₹{project.amount_pending}"
                )
                return redirect('record_client_payment', project_id=project_id)
            
            # Get company funds
            company_funds = CompanyFunds.objects.get(id=1)
            
            # Create fund transaction (CREDIT)
            fund_txn = FundTransaction.objects.create(
                transaction_type='client_payment',
                amount=amount,
                is_credit=True,
                balance_after=company_funds.total_funds + amount,
                project=project,
                description=f"Payment received for {project.project_name}",
                created_by_name=request.session.get('full_name'),
                created_by_role=request.session.get('role')
            )
            
            # Create project payment record
            ProjectPayment.objects.create(
                project=project,
                amount_paid=amount,
                payment_date=payment_date,
                payment_method=payment_method,
                payment_reference=payment_reference,
                payment_proof=payment_proof,
                remarks=remarks,
                recorded_by_name=request.session.get('full_name'),
                recorded_by_role=request.session.get('role'),
                fund_transaction=fund_txn
            )
            
            # Update company funds
            company_funds.total_funds += amount
            company_funds.total_received_from_clients += amount
            company_funds.total_profit = (
                company_funds.total_received_from_clients - 
                company_funds.total_paid_as_salary
            )
            company_funds.save()
            
            # Update project payment status
            project.update_payment_status()
            
            messages.success(request, 
                f"✅ Payment of ₹{amount} recorded! "
                f"Remaining: ₹{project.amount_pending}"
            )
            return redirect('project_financial_detail', id=project_id)
            
        except Exception as e:
            messages.error(request, f"❌ Error: {str(e)}")
    
    context = {
        'project': project,
        'today': date.today().isoformat()
    }
    return render(request, 'projects/record_client_payment.html', context)


@check_blocked_user
@login_required
@role_required(['super_admin', 'admin'])
def project_financial_detail(request, id):
    """
    Detailed payment history for a project
    """
    project = get_object_or_404(Project, id=id)
    payments = ProjectPayment.objects.filter(project=project)
    
    context = {
        'project': project,
        'payments': payments
    }
    return render(request, 'projects/project_financial_detail.html', context)





# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- DAILY WORK REPORTS =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# ADD DAILY WORK REPORT (For Developers & SEOs)
@check_blocked_user
@login_required
@role_required(['developer', 'seos','digital_marketing'])
def add_work_report(request):
    user_id = request.session.get('user_id')
    user_role = request.session.get('role')
    
    # Get only projects assigned to this employee
    assigned_projects = Project.objects.filter(
        assignments__employee_id=user_id,
        assignments__is_active=True,
        is_active=True
    ).distinct()
    
    if request.method == "POST":
        try:
            project_id = request.POST.get('project_id')
            project = get_object_or_404(Project, id=project_id)
            employee = get_object_or_404(Employee, id=user_id)
            
            work_date = request.POST.get('work_date')
            
            # Check if report already exists for this date
            existing_report = DailyWorkReport.objects.filter(
                project=project,
                employee=employee,
                work_date=work_date
            ).first()
            
            if existing_report:
                messages.warning(request, f"You have already submitted a report for {project.project_name} on {work_date}!")
                return redirect('my_work_reports')
            
            # Handle file uploads
            attachment_1 = request.FILES.get('attachment_1')
            attachment_2 = request.FILES.get('attachment_2')
            attachment_3 = request.FILES.get('attachment_3')
            
            # Create Work Report
            report = DailyWorkReport.objects.create(
                project=project,
                project_id_display=project.project_id,
                project_name=project.project_name,
                project_type=project.project_type,
                employee=employee,
                employee_id_display=employee.employee_id,
                employee_name=employee.full_name,
                employee_role=employee.role,
                work_date=work_date,
                hours_worked=request.POST.get('hours_worked'),
                tasks_completed=request.POST.get('tasks_completed'),
                tasks_in_progress=request.POST.get('tasks_in_progress'),
                tasks_planned=request.POST.get('tasks_planned'),
                challenges_faced=request.POST.get('challenges_faced'),
                support_needed=request.POST.get('support_needed'),
                overall_status=request.POST.get('overall_status'),
                additional_notes=request.POST.get('additional_notes'),
                attachment_1=attachment_1,
                attachment_2=attachment_2,
                attachment_3=attachment_3
            )
            
            messages.success(request, f"Work report {report.report_id} submitted successfully!")
            return redirect('my_work_reports')
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    context = {
        'assigned_projects': assigned_projects,
        'today': date.today().isoformat()
    }
    return render(request, 'Reports/add_work_report.html', context)


# MY WORK REPORTS (Employee View)
@check_blocked_user
@login_required
@role_required(['developer', 'seos','digital_marketing'])
def my_work_reports(request):
    user_id = request.session.get('user_id')
    reports = DailyWorkReport.objects.filter(employee_id=user_id, is_active=True)
    
    context = {'reports': reports}
    return render(request, 'Reports/my_work_reports.html', context)


# ALL WORK REPORTS (Admin/Super Admin View)
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def all_work_reports(request):
    reports = DailyWorkReport.objects.filter(is_active=True)
    
    # Filter options
    employee_filter = request.GET.get('employee')
    project_filter = request.GET.get('project')
    date_filter = request.GET.get('date')
    status_filter = request.GET.get('status')
    
    if employee_filter:
        reports = reports.filter(employee_id=employee_filter)
    if project_filter:
        reports = reports.filter(project_id=project_filter)
    if date_filter:
        reports = reports.filter(work_date=date_filter)
    if status_filter:
        reports = reports.filter(overall_status=status_filter)
    
    # Get distinct employees and projects for filter dropdowns
    employees = Employee.objects.filter(
        role__in=['developer', 'seos'],
        is_active=True
    )
    projects = Project.objects.filter(is_active=True)
    
    context = {
        'reports': reports,
        'employees': employees,
        'projects': projects
    }
    return render(request, 'Reports/all_work_reports.html', context)


# VIEW WORK REPORT DETAIL
@check_blocked_user
@login_required
def view_work_report(request, id):
    report = get_object_or_404(DailyWorkReport, id=id)
    
    user_role = request.session.get('role')
    user_id = request.session.get('user_id')
    
    # Check access permissions
    if user_role in ['developer', 'seos']:
        if report.employee_id != user_id:
            messages.error(request, "You can only view your own reports!")
            return redirect('my_work_reports')
    
    context = {'report': report}
    return render(request, 'Reports/view_work_report.html', context)


# EDIT WORK REPORT (Only if not reviewed yet)
@check_blocked_user
@login_required
@role_required(['developer', 'seos','digital_marketing'])
def edit_work_report(request, id):
    report = get_object_or_404(DailyWorkReport, id=id)
    user_id = request.session.get('user_id')
    
    # Check ownership
    if report.employee_id != user_id:
        messages.error(request, "You can only edit your own reports!")
        return redirect('my_work_reports')
    
    # Check if already reviewed
    if report.is_reviewed:
        messages.warning(request, "Cannot edit - Report has been reviewed by admin!")
        return redirect('view_work_report', id=id)
    
    if request.method == "POST":
        try:
            report.work_date = request.POST.get('work_date')
            report.hours_worked = request.POST.get('hours_worked')
            report.tasks_completed = request.POST.get('tasks_completed')
            report.tasks_in_progress = request.POST.get('tasks_in_progress')
            report.tasks_planned = request.POST.get('tasks_planned')
            report.challenges_faced = request.POST.get('challenges_faced')
            report.support_needed = request.POST.get('support_needed')
            report.overall_status = request.POST.get('overall_status')
            report.additional_notes = request.POST.get('additional_notes')
            
            # Update attachments if new ones uploaded
            if request.FILES.get('attachment_1'):
                report.attachment_1 = request.FILES.get('attachment_1')
            if request.FILES.get('attachment_2'):
                report.attachment_2 = request.FILES.get('attachment_2')
            if request.FILES.get('attachment_3'):
                report.attachment_3 = request.FILES.get('attachment_3')
            
            report.save()
            
            messages.success(request, f"Report {report.report_id} updated successfully!")
            return redirect('my_work_reports')
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    context = {'report': report}
    return render(request, 'Reports/edit_work_report.html', context)


# DELETE WORK REPORT
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def delete_work_report(request, id):
    report = get_object_or_404(DailyWorkReport, id=id)
    user_role = request.session.get('role')
    user_id = request.session.get('user_id')
    
    # Only employee can delete their own unreviewd reports or admin can delete any
    if user_role in ['developer', 'seos']:
        if report.employee_id != user_id:
            messages.error(request, "You can only delete your own reports!")
            return redirect('my_work_reports')
        if report.is_reviewed:
            messages.warning(request, "Cannot delete - Report has been reviewed!")
            return redirect('my_work_reports')
    
    report_id = report.report_id
    report.delete()
    messages.success(request, f"Report {report_id} deleted successfully!")
    
    if user_role in ['admin', 'super_admin']:
        return redirect('all_work_reports')
    else:
        return redirect('my_work_reports')


# ADMIN REVIEW REPORT
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin'])
def review_work_report(request, id):
    report = get_object_or_404(DailyWorkReport, id=id)
    
    if request.method == "POST":
        from django.utils import timezone
        
        report.is_reviewed = True
        report.reviewed_by_name = request.session.get('full_name')
        report.reviewed_by_role = request.session.get('role')
        report.review_date = timezone.now()
        report.admin_feedback = request.POST.get('admin_feedback')
        report.save()
        
        messages.success(request, f"Report {report.report_id} reviewed successfully!")
        return redirect('all_work_reports')
    
    context = {'report': report}
    return render(request, 'Reports/review_work_report.html', context)


# AJAX: Get Project Details
@check_blocked_user
@login_required
def get_project_details(request):
    try:
        project_id = request.GET.get('project_id')
        project = Project.objects.get(id=project_id)
        
        data = {
            'success': True,
            'project_id': project.project_id,
            'project_name': project.project_name,
            'project_type': project.project_type,
            'client_name': project.client.company_name,
            'deadline': project.deadline.isoformat(),
            'status': project.status,
            'description': project.description
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    






# =-=-=-=-=-=-=-=-=-=-=-=-= Holiday Master =-=-=-=-=-=-=-=-=-=-=-=-=-=

# ADD HOLIDAY
@check_blocked_user
@login_required
@role_required(['super_admin'])
def add_holiday(request):
    if request.method == "POST":
        try:
            holiday_name = request.POST.get('holiday_name')
            holiday_date = request.POST.get('holiday_date')
            holiday_type = request.POST.get('holiday_type')
            description = request.POST.get('description')
            
            user_name = request.session.get('full_name')
            user_role = request.session.get('role')
            
            # Check if holiday already exists for this date
            existing = HolidayMaster.objects.filter(holiday_date=holiday_date).first()
            if existing:
                messages.warning(request, f"Holiday already exists for {holiday_date}: {existing.holiday_name}")
                return redirect('add_holiday')
            
            holiday = HolidayMaster.objects.create(
                holiday_name=holiday_name,
                holiday_date=holiday_date,
                holiday_type=holiday_type,
                description=description,
                created_by_name=user_name,
                created_by_role=user_role
            )
            
            messages.success(request, f"Holiday '{holiday.holiday_name}' added successfully for {holiday_date}!")
            return redirect('holiday_list')
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    context = {
        'today': date.today().isoformat()
    }
    return render(request, 'Holiday/add_holiday.html', context)


# HOLIDAY LIST
# @check_blocked_user
# @login_required
# @role_required(['super_admin', 'admin', 'hr'])
# def holiday_list(request):
#     # Get year filter (default current year)
#     current_year = datetime.now().year
#     year_filter = request.GET.get('year', current_year)
    
#     # Fetch holidays for selected year
#     # CHANGE: Removed is_active=True filter because we are now permanently deleting records.
#     holidays_list = HolidayMaster.objects.filter(
#         holiday_date__year=year_filter
#     ).order_by('holiday_date')
    
#     # Get available years for filter
#     years = HolidayMaster.objects.dates('holiday_date', 'year', order='DESC')
    
#     # Pagination
#     paginator = Paginator(holidays_list, 10)  # Show 10 holidays per page
#     page = request.GET.get('page')
    
#     try:
#         holidays = paginator.page(page)
#     except PageNotAnInteger:
#         # If page is not an integer, deliver first page
#         holidays = paginator.page(1)
#     except EmptyPage:
#         # If page is out of range, deliver last page
#         holidays = paginator.page(paginator.num_pages)
    
#     context = {
#         'holidays': holidays,
#         'years': years,
#         'selected_year': int(year_filter),
#         'current_year': current_year
#     }
    
#     return render(request, 'holiday/holiday_list.html', context)


@check_blocked_user
@login_required
@role_required(['super_admin', 'admin', 'hr'])
def holiday_list(request):
    current_year = datetime.now().year

    # ✅ FIX 1: year ko hamesha int banao
    try:
        year_filter = int(request.GET.get('year', current_year))
    except ValueError:
        year_filter = current_year

    # Fetch holidays for selected year
    holidays_list = HolidayMaster.objects.filter(
        holiday_date__year=year_filter
    ).order_by('holiday_date')

    # Available years
    years = HolidayMaster.objects.dates('holiday_date', 'year', order='DESC')

    # Pagination
    paginator = Paginator(holidays_list, 10)

    # ✅ FIX 2: default page = 1
    page = request.GET.get('page', 1)

    try:
        holidays = paginator.page(page)
    except PageNotAnInteger:
        holidays = paginator.page(1)
    except EmptyPage:
        holidays = paginator.page(paginator.num_pages)

    context = {
        'holidays': holidays,
        'years': years,
        'selected_year': year_filter,   # already int
        'current_year': current_year
    }

    return render(request, 'holiday/holiday_list.html', context)



# EDIT HOLIDAY
@check_blocked_user
@login_required
@role_required(['super_admin'])
def edit_holiday(request, id):
    holiday = get_object_or_404(HolidayMaster, id=id)
    
    if request.method == "POST":
        try:
            holiday.holiday_name = request.POST.get('holiday_name')
            holiday.holiday_date = request.POST.get('holiday_date')
            holiday.holiday_type = request.POST.get('holiday_type')
            holiday.description = request.POST.get('description')
            holiday.save()
            
            messages.success(request, f"Holiday '{holiday.holiday_name}' updated successfully!")
            return redirect('holiday_list')
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    context = {'holiday': holiday}
    return render(request, 'Holiday/edit_holiday.html', context)


# DELETE HOLIDAY
@check_blocked_user
@login_required
@role_required(['super_admin'])
def delete_holiday(request, id):
    holiday = get_object_or_404(HolidayMaster, id=id)
    holiday_name = holiday.holiday_name
    holiday_date = holiday.holiday_date
    
    # CHANGE: Permanent deletion instead of soft delete.
    # The record will be completely removed from the database.
    holiday.delete()
    
    messages.success(request, f"Holiday '{holiday_name}' on {holiday_date} deleted successfully!")
    return redirect('holiday_list')


# VIEW UPCOMING HOLIDAYS (For all employees)
@check_blocked_user
@login_required
def upcoming_holidays(request):
    today = datetime.now().date()
    next_3_months = today + timedelta(days=90)
    
    # CHANGE: Removed is_active=True filter.
    holidays = HolidayMaster.objects.filter(
        holiday_date__gte=today,
        holiday_date__lte=next_3_months
    ).order_by('holiday_date')
    
    context = {'holidays': holidays}
    return render(request, 'Holiday/upcoming_holidays.html', context)


# ==================== CLEAN LEAVE & ATTENDANCE VIEWS ====================

def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine formula - returns distance in meters"""
    R = 6371000
    lat1_rad = math.radians(float(lat1))
    lat2_rad = math.radians(float(lat2))
    delta_lat = math.radians(float(lat2) - float(lat1))
    delta_lon = math.radians(float(lon2) - float(lon1))
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def check_geofence(user_lat, user_lon):
    """Check if within 70m radius"""
    config = GeofenceConfig.objects.filter(is_active=True).first()
    
    if not config:
        office_lat = Decimal('23.351633')
        office_lon = Decimal('85.3162779')
        radius = 70
    else:
        office_lat = config.latitude
        office_lon = config.longitude
        radius = config.radius_meters
    
    distance = calculate_distance(user_lat, user_lon, office_lat, office_lon)
    is_within = distance <= radius
    
    return is_within, round(distance, 2), config


# ==================== LEAVE MANAGEMENT ====================

@check_blocked_user
@login_required
@role_required(['hr', 'sales', 'developer', 'seos','digital_marketing' ,'admin'])
def apply_leave(request):
    """Apply for leave - 1 Casual/month + 6 Sick/year"""
    user_id = request.session.get('user_id')
    employee = get_object_or_404(Employee, id=user_id)
    
    # Get/create leave balance
    leave_balance, created = EmployeeLeaveBalance.objects.get_or_create(
        employee=employee,
        defaults={
            'sick_leave_balance': Decimal('6.0'),
            'current_year': timezone.now().year,
            'current_month': timezone.now().month,
            'casual_leaves_taken_this_month': 0
        }
    )
    
    # 🔥 AUTO-RESET: Check if month/year changed
    now = timezone.now()
    if leave_balance.current_month != now.month or leave_balance.current_year != now.year:
        # New month = reset casual counter
        if leave_balance.current_month != now.month:
            leave_balance.casual_leaves_taken_this_month = 0
        
        # New year = reset sick leaves
        if leave_balance.current_year < now.year:
            leave_balance.sick_leave_balance = Decimal('6.0')
            leave_balance.casual_leaves_taken_this_month = 0
        
        leave_balance.current_month = now.month
        leave_balance.current_year = now.year
        leave_balance.save()
    
    # Calculate available leaves
    casual_available_this_month = max(0, 1 - leave_balance.casual_leaves_taken_this_month)
    sick_available = float(leave_balance.sick_leave_balance)
    
    if request.method == "POST":
        try:
            leave_type = request.POST.get('leave_type')
            from_date_obj = datetime.strptime(request.POST.get('from_date'), '%Y-%m-%d').date()
            to_date_obj = datetime.strptime(request.POST.get('to_date'), '%Y-%m-%d').date()
            
            # Calculate working days (exclude Sundays + holidays)
            total_days = 0
            current_date = from_date_obj
            
            while current_date <= to_date_obj:
                if current_date.weekday() != 6:  # Not Sunday
                    if not HolidayMaster.objects.filter(holiday_date=current_date, is_active=True).exists():
                        total_days += 1
                current_date += timedelta(days=1)
            
            if total_days <= 0:
                messages.warning(request, "❌ Selected dates are all holidays/Sundays!")
                return redirect('apply_leave')
            
            # Check overlapping leaves
            if LeaveApplication.objects.filter(
                employee=employee,
                from_date__lte=to_date_obj,
                to_date__gte=from_date_obj,
                status__in=['pending', 'approved']
            ).exists():
                messages.error(request, "❌ You already have a leave application for these dates!")
                return redirect('apply_leave')
            
            # Determine leave distribution based on type
            casual_requested = 0
            sick_requested = 0
            
            if leave_type == 'casual':
                casual_requested = total_days
                
                # 🔥 JUST SHOW INFO MESSAGE, DON'T BLOCK SUBMISSION
                if casual_requested > casual_available_this_month:
                    unpaid = casual_requested - casual_available_this_month
                    messages.warning(request, 
                        f"⚠️ Note: You requested {casual_requested} days but only have {casual_available_this_month} casual leave. "
                        f"{unpaid} day(s) will be marked as UNPAID."
                    )
            
            elif leave_type == 'sick':
                sick_requested = total_days
                
                # 🔥 JUST SHOW INFO MESSAGE, DON'T BLOCK
                if sick_requested > sick_available:
                    unpaid = sick_requested - int(sick_available)
                    messages.warning(request, 
                        f"⚠️ Note: You requested {sick_requested} days but only have {int(sick_available)} sick leaves. "
                        f"{unpaid} day(s) will be marked as UNPAID."
                    )
            
            elif leave_type == 'combined':
                casual_requested = int(request.POST.get('casual_days', '0'))
                sick_requested = int(request.POST.get('sick_days', '0'))
                
                # Validate total distribution
                if casual_requested + sick_requested != total_days:
                    messages.error(request, 
                        f"❌ Distribution mismatch! Total should be {total_days} days, "
                        f"but you entered {casual_requested + sick_requested}."
                    )
                    return redirect('apply_leave')
                
                # Check if exceeds limits (just warn, don't block)
                if casual_requested > casual_available_this_month:
                    messages.warning(request, 
                        f"⚠️ Casual: {casual_requested - casual_available_this_month} day(s) will be UNPAID"
                    )
                
                if sick_requested > sick_available:
                    messages.warning(request, 
                        f"⚠️ Sick: {sick_requested - int(sick_available)} day(s) will be UNPAID"
                    )
            
            # 🔥 CREATE APPLICATION - NO MORE BLOCKING
            LeaveApplication.objects.create(
                employee=employee,
                employee_id_display=employee.employee_id,
                employee_name=employee.full_name,
                employee_role=employee.role,
                leave_type=leave_type,
                from_date=from_date_obj,
                to_date=to_date_obj,
                total_days=total_days,
                casual_days_requested=casual_requested,
                sick_days_requested=sick_requested,
                reason=request.POST.get('reason'),
                attachment=request.FILES.get('attachment'),
                status='pending'
            )
            
            messages.success(request, 
                f"✅ Leave application submitted successfully! "
                f"Total: {total_days} days (Pending HR approval)"
            )
            return redirect('my_leave_applications')
            
        except Exception as e:
            messages.error(request, f"❌ Error: {str(e)}")
            return redirect('apply_leave')
    
    return render(request, 'Leave/apply_leave.html', {
        'employee': employee,
        'leave_balance': leave_balance,
        'casual_available_this_month': casual_available_this_month,
        'sick_available': sick_available,
        'today': date.today().isoformat()
    })


@check_blocked_user
@login_required
@role_required(['hr', 'sales', 'developer', 'seos','digital_marketing' ,'admin'])
def my_leave_applications(request):
    """Employee's leave list"""
    user_id = request.session.get('user_id')
    employee = get_object_or_404(Employee, id=user_id)
    
    return render(request, 'Leave/my_leave_applications.html', {
        'applications': LeaveApplication.objects.filter(employee=employee, is_active=True).order_by('-applied_date'),
        'leave_balance': EmployeeLeaveBalance.objects.filter(employee=employee).first()
    })


@check_blocked_user
@login_required
@role_required(['hr', 'admin', 'super_admin'])
def pending_leave_requests(request):
    """HR pending leaves"""
    return render(request, 'Leave/pending_leave_requests.html', {
        'pending_leaves': LeaveApplication.objects.filter(status='pending', is_active=True).order_by('-applied_date')
    })


# @check_blocked_user
# @login_required
# @role_required(['hr', 'admin', 'super_admin'])
# def approve_reject_leave(request, id):
#     """
#     Approve/Reject with smart deduction:
#     1. Deduct from available leaves
#     2. Excess becomes unpaid
#     3. Create attendance: Paid = 'L', Unpaid = 'A'
#     """
#     leave_app = get_object_or_404(LeaveApplication, id=id)
    
#     if request.method == "POST":
#         action = request.POST.get('action')
        
#         if action == 'approve':
#             leave_app.status = 'approved'
#             leave_balance = leave_app.employee.leave_balance
            
#             casual_to_deduct = leave_app.casual_days_requested
#             sick_to_deduct = leave_app.sick_days_requested
#             unpaid_days = 0
            
#             # 🔥 Deduct Casual (check monthly limit)
#             if casual_to_deduct > 0:
#                 # Get available casual for the month of leave application
#                 now = timezone.now()
#                 if leave_balance.current_month != now.month or leave_balance.current_year != now.year:
#                     leave_balance.casual_leaves_taken_this_month = 0
#                     leave_balance.current_month = now.month
#                     leave_balance.current_year = now.year
#                     leave_balance.save()
                
#                 available_casual = max(0, 1 - leave_balance.casual_leaves_taken_this_month)
                
#                 if available_casual >= casual_to_deduct:
#                     leave_balance.casual_leaves_taken_this_month += casual_to_deduct
#                     leave_app.casual_days_deducted = casual_to_deduct
#                 else:
#                     # Use available, rest becomes unpaid
#                     leave_balance.casual_leaves_taken_this_month += available_casual
#                     leave_app.casual_days_deducted = available_casual
#                     unpaid_days += (casual_to_deduct - available_casual)
            
#             # 🔥 Deduct Sick
#             if sick_to_deduct > 0:
#                 available_sick = float(leave_balance.sick_leave_balance)
                
#                 if available_sick >= sick_to_deduct:
#                     leave_balance.sick_leave_balance -= Decimal(str(sick_to_deduct))
#                     leave_app.sick_days_deducted = sick_to_deduct
#                 else:
#                     # Use available, rest becomes unpaid
#                     leave_app.sick_days_deducted = int(available_sick)
#                     leave_balance.sick_leave_balance = Decimal('0')
#                     unpaid_days += (sick_to_deduct - int(available_sick))
            
#             leave_app.unpaid_days = unpaid_days
#             leave_balance.save()
            
#             # 🔥 CREATE ATTENDANCE: Paid = 'L', Unpaid = 'A'
#             current_date = leave_app.from_date
#             days_processed = 0
#             paid_days_remaining = leave_app.casual_days_deducted + leave_app.sick_days_deducted
            
#             while current_date <= leave_app.to_date:
#                 if current_date.weekday() != 6:  # Not Sunday
#                     if not HolidayMaster.objects.filter(holiday_date=current_date, is_active=True).exists():
#                         days_processed += 1
                        
#                         # 🔥 LOGIC: First N days = Paid (L), Rest = Unpaid (A)
#                         if days_processed <= paid_days_remaining:
#                             status = 'on_leave'  # Paid leave
#                         else:
#                             status = 'absent'  # Unpaid = Absent
                        
#                         Attendance.objects.update_or_create(
#                             employee=leave_app.employee,
#                             attendance_date=current_date,
#                             defaults={
#                                 'employee_id_display': leave_app.employee.employee_id,
#                                 'employee_name': leave_app.employee.full_name,
#                                 'status': status,
#                                 'leave_application': leave_app,
#                                 'auto_calculated': False,
#                                 'remarks': f'Leave approved by {request.session.get("full_name")}' if status == 'on_leave' else f'Unpaid leave (marked absent)'
#                             }
#                         )
                
#                 current_date += timedelta(days=1)
            
#             if unpaid_days > 0:
#                 messages.warning(request, 
#                     f"✅ Approved! Deducted: Casual={leave_app.casual_days_deducted}, "
#                     f"Sick={leave_app.sick_days_deducted}. "
#                     f"⚠️ {unpaid_days} unpaid days marked as ABSENT."
#                 )
#             else:
#                 messages.success(request, 
#                     f"✅ Approved! Deducted: Casual={leave_app.casual_days_deducted}, "
#                     f"Sick={leave_app.sick_days_deducted}"
#                 )
        
#         else:  # Reject
#             leave_app.status = 'rejected'
#             messages.info(request, "❌ Leave application rejected!")
        
#         # Save approval details
#         leave_app.approved_by_name = request.session.get('full_name')
#         leave_app.approved_by_role = request.session.get('role')
#         leave_app.approval_date = timezone.now()
#         leave_app.hr_remarks = request.POST.get('hr_remarks')
#         leave_app.save()
        
#         return redirect('pending_leave_requests')
    
#     return render(request, 'Leave/approve_reject_leave.html', {
#         'leave_app': leave_app
#     })


@check_blocked_user
@login_required
@role_required(['hr', 'admin', 'super_admin'])
def approve_reject_leave(request, id):
    """
    🔥 UPDATED: Approve/Reject with LWP logic
    - Paid leaves → 'on_leave' (L)
    - Unpaid leaves → 'lwp' (LWP) instead of 'absent'
    """
    leave_app = get_object_or_404(LeaveApplication, id=id)
    
    if request.method == "POST":
        action = request.POST.get('action')
        
        if action == 'approve':
            leave_app.status = 'approved'
            leave_balance = leave_app.employee.leave_balance
            
            casual_to_deduct = leave_app.casual_days_requested
            sick_to_deduct = leave_app.sick_days_requested
            unpaid_days = 0
            
            # 🔥 Deduct Casual (check monthly limit)
            if casual_to_deduct > 0:
                now = timezone.now()
                if leave_balance.current_month != now.month or leave_balance.current_year != now.year:
                    leave_balance.casual_leaves_taken_this_month = 0
                    leave_balance.current_month = now.month
                    leave_balance.current_year = now.year
                    leave_balance.save()
                
                available_casual = max(0, 1 - leave_balance.casual_leaves_taken_this_month)
                
                if available_casual >= casual_to_deduct:
                    leave_balance.casual_leaves_taken_this_month += casual_to_deduct
                    leave_app.casual_days_deducted = casual_to_deduct
                else:
                    leave_balance.casual_leaves_taken_this_month += available_casual
                    leave_app.casual_days_deducted = available_casual
                    unpaid_days += (casual_to_deduct - available_casual)
            
            # 🔥 Deduct Sick
            if sick_to_deduct > 0:
                available_sick = float(leave_balance.sick_leave_balance)
                
                if available_sick >= sick_to_deduct:
                    leave_balance.sick_leave_balance -= Decimal(str(sick_to_deduct))
                    leave_app.sick_days_deducted = sick_to_deduct
                else:
                    leave_app.sick_days_deducted = int(available_sick)
                    leave_balance.sick_leave_balance = Decimal('0')
                    unpaid_days += (sick_to_deduct - int(available_sick))
            
            leave_app.unpaid_days = unpaid_days
            leave_balance.save()
            
            # 🔥 CREATE ATTENDANCE: Paid = 'on_leave' (L), Unpaid = 'lwp' (LWP)
            current_date = leave_app.from_date
            days_processed = 0
            paid_days_remaining = leave_app.casual_days_deducted + leave_app.sick_days_deducted
            
            while current_date <= leave_app.to_date:
                if current_date.weekday() != 6:  # Not Sunday
                    if not HolidayMaster.objects.filter(holiday_date=current_date, is_active=True).exists():
                        days_processed += 1
                        
                        # 🔥 LOGIC: First N days = Paid (L), Rest = Unpaid (LWP)
                        if days_processed <= paid_days_remaining:
                            status = 'on_leave'  # Paid leave
                            remark = f'Paid leave approved by {request.session.get("full_name")}'
                        else:
                            status = 'lwp'  # 🔥 CHANGED: Use LWP instead of absent
                            remark = f'Leave Without Pay (no balance) - approved by {request.session.get("full_name")}'
                        
                        Attendance.objects.update_or_create(
                            employee=leave_app.employee,
                            attendance_date=current_date,
                            defaults={
                                'employee_id_display': leave_app.employee.employee_id,
                                'employee_name': leave_app.employee.full_name,
                                'status': status,
                                'leave_application': leave_app,
                                'auto_calculated': False,
                                'remarks': remark
                            }
                        )
                
                current_date += timedelta(days=1)
            
            if unpaid_days > 0:
                messages.warning(request, 
                    f"✅ Approved! Deducted: Casual={leave_app.casual_days_deducted}, "
                    f"Sick={leave_app.sick_days_deducted}. "
                    f"⚠️ {unpaid_days} unpaid days marked as LWP (Leave Without Pay)."
                )
            else:
                messages.success(request, 
                    f"✅ Approved! Deducted: Casual={leave_app.casual_days_deducted}, "
                    f"Sick={leave_app.sick_days_deducted}"
                )
        
        else:  # Reject
            leave_app.status = 'rejected'
            messages.info(request, "❌ Leave application rejected!")
        
        # Save approval details
        leave_app.approved_by_name = request.session.get('full_name')
        leave_app.approved_by_role = request.session.get('role')
        leave_app.approval_date = timezone.now()
        leave_app.hr_remarks = request.POST.get('hr_remarks')
        leave_app.save()
        
        return redirect('pending_leave_requests')
    
    return render(request, 'Leave/approve_reject_leave.html', {
        'leave_app': leave_app
    })


@check_blocked_user
@login_required
@role_required(['hr', 'admin', 'super_admin'])
def refund_leave(request, leave_id):
    """Refund when employee returns early"""
    leave_app = get_object_or_404(LeaveApplication, id=leave_id)
    
    if request.method == "POST":
        actual_days = Decimal(request.POST.get('actual_days'))
        refund_days = (leave_app.casual_days_deducted + leave_app.sick_days_deducted) - actual_days
        
        if refund_days > 0:
            leave_balance = leave_app.employee.leave_balance
            
            # Refund Casual first
            casual_refund = min(refund_days, leave_app.casual_days_deducted)
            sick_refund = refund_days - casual_refund
            
            leave_balance.casual_leave_balance += casual_refund
            leave_balance.sick_leave_balance += sick_refund
            leave_balance.save()
            
            leave_app.days_actually_taken = actual_days
            leave_app.refund_processed = True
            leave_app.save()
            
            messages.success(request, f"✅ Refunded! C:{casual_refund} S:{sick_refund}")
    
    return redirect('all_leave_applications')


@check_blocked_user
@login_required
@role_required(['hr', 'admin', 'super_admin'])
def all_leave_applications(request):
    """
    HR/Admin view: All leave applications with filters
    """
    # Get all employees for filter dropdown
    employees = Employee.objects.filter(is_active=True).order_by('full_name')
    
    # Base queryset
    applications = LeaveApplication.objects.filter(is_active=True).select_related('employee')
    
    # Apply filters
    employee_filter = request.GET.get('employee')
    if employee_filter:
        applications = applications.filter(employee_id=employee_filter)
    
    status_filter = request.GET.get('status')
    if status_filter:
        applications = applications.filter(status=status_filter)
    
    month_filter = request.GET.get('month')
    if month_filter:
        try:
            year, month = month_filter.split('-')
            applications = applications.filter(
                from_date__year=year,
                from_date__month=month
            )
        except:
            pass
    
    applications = applications.order_by('-applied_date')
    
    return render(request, 'Leave/all_leave_applications.html', {
        'applications': applications,
        'employees': employees
    })


@check_blocked_user
@login_required
def view_leave_detail(request, id):
    """
    Detailed view of a single leave application
    Accessible by: Employee (their own) + HR/Admin (all)
    """
    leave_app = get_object_or_404(LeaveApplication, id=id, is_active=True)
    user_id = request.session.get('user_id')
    user_role = request.session.get('role')
    
    # Permission check: Employee can only view their own, HR/Admin can view all
    if user_role not in ['hr', 'admin', 'super_admin']:
        if leave_app.employee.id != user_id:
            messages.error(request, "❌ You don't have permission to view this leave application!")
            return redirect('my_leave_applications')
    
    return render(request, 'Leave/view_leave_detail.html', {
        'leave_app': leave_app
    })


# ==================== GEOFENCING ATTENDANCE ====================

# Helper function for auto absent if not login
def mark_absent_for_past_dates(employee=None):
    """
    Auto-mark absent for employees who didn't check-in
    If employee provided, only check that employee
    Otherwise check all active employees
    """
    today = timezone.now().date()
    
    # Get employees to check
    if employee:
        employees = [employee]
    else:
        employees = Employee.objects.filter(is_active=True)
    
    marked_count = 0
    
    # Check last 60 days
    for days_ago in range(1, 61):
        check_date = today - timedelta(days=days_ago)
        
        # Skip Sundays
        if check_date.weekday() == 6:
            continue
        
        # Skip holidays
        if HolidayMaster.objects.filter(holiday_date=check_date, is_active=True).exists():
            continue
        
        for emp in employees:
            # Check if attendance already exists
            if Attendance.objects.filter(employee=emp, attendance_date=check_date).exists():
                continue
            
            # Check if any punch exists
            if AttendancePunch.objects.filter(employee=emp, punch_date=check_date).exists():
                continue
            
            # Mark absent
            Attendance.objects.create(
                employee=emp,
                employee_id_display=emp.employee_id,
                employee_name=emp.full_name,
                attendance_date=check_date,
                status='absent',
                check_in_time=None,
                check_out_time=None,
                total_work_hours=0,
                total_break_minutes=0,
                is_late=False,
                auto_calculated=True,
                remarks='Auto-marked absent - No check-in'
            )
            marked_count += 1
    
    return marked_count


@check_blocked_user
@login_required
@role_required(['hr', 'sales', 'developer', 'seos','digital_marketing' ,'admin'])
def punch_attendance(request):
    """
    Modified - Auto marks absent for logged-in employee when they open punch page
    """
    user_id = request.session.get('user_id')
    employee = get_object_or_404(Employee, id=user_id)
    
    # Auto-mark absent for THIS employee only (faster)
    mark_absent_for_past_dates(employee)
    
    today = timezone.now().date()
    
    today_punches = AttendancePunch.objects.filter(employee=employee, punch_date=today).order_by('punch_datetime')
    today_breaks = BreakLog.objects.filter(employee=employee, attendance_date=today)
    
    last_punch = today_punches.last()
    is_checked_in = last_punch and last_punch.punch_type in ['check_in', 'break_end']
    is_on_break = last_punch and last_punch.punch_type == 'break_start'
    
    return render(request, 'Attendance/punch_attendance.html', {
        'employee': employee,
        'today_punches': today_punches,
        'today_breaks': today_breaks,
        'is_checked_in': is_checked_in,
        'is_on_break': is_on_break,
        'config': GeofenceConfig.objects.filter(is_active=True).first()
    })


# @check_blocked_user
# @login_required
# @role_required(['hr', 'sales', 'developer', 'seos','digital_marketing' ,'admin'])
# def process_punch(request):
#     """Process punch with geofence + allow only 1 check-in & 1 check-out per day"""
#     if request.method == "POST":
#         try:
#             user_id = request.session.get('user_id')
#             employee = get_object_or_404(Employee, id=user_id)

#             punch_type = request.POST.get('punch_type')
#             user_lat = Decimal(request.POST.get('latitude'))
#             user_lon = Decimal(request.POST.get('longitude'))

#             today = timezone.now().date()

#             # Fetch today's punches
#             today_punches = AttendancePunch.objects.filter(
#                 employee=employee,
#                 punch_date=today
#             ).order_by('punch_datetime')

#             # Check rules: Only ONE check-in allowed
#             if punch_type == "check_in":
#                 if today_punches.filter(punch_type='check_in').exists():
#                     return JsonResponse({
#                         'success': False,
#                         'message': '❌ You already checked-in today.'
#                     })

#             # Check rules: Only ONE check-out allowed
#             if punch_type == "check_out":
#                 if not today_punches.filter(punch_type='check_in').exists():
#                     return JsonResponse({
#                         'success': False,
#                         'message': '❌ You must check-in first.'
#                     })

#                 if today_punches.filter(punch_type='check_out').exists():
#                     return JsonResponse({
#                         'success': False,
#                         'message': '❌ You have already checked-out today.'
#                     })

#             # If already checked-out → NO MORE punch actions allowed
#             if today_punches.filter(punch_type='check_out').exists():
#                 return JsonResponse({
#                     'success': False,
#                     'message': '❌ You have already completed your day. No more punches allowed today.'
#                 })

#             # Cannot start break without check-in
#             if punch_type == "break_start":
#                 last_p = today_punches.last()
#                 if not last_p or last_p.punch_type != "check_in" and last_p.punch_type != "break_end":
#                     return JsonResponse({
#                         'success': False,
#                         'message': "❌ You must be checked-in to start a break."
#                     })

#             # Cannot end break without starting break
#             if punch_type == "break_end":
#                 last_break_start = today_punches.filter(punch_type='break_start').last()
#                 last_break_end = today_punches.filter(punch_type='break_end').last()

#                 if not last_break_start:
#                     return JsonResponse({
#                         'success': False,
#                         'message': "❌ No break started."
#                     })

#                 if last_break_end and last_break_end.punch_datetime > last_break_start.punch_datetime:
#                     return JsonResponse({
#                         'success': False,
#                         'message': "❌ Break already ended."
#                     })

#             # GEO-FENCE CHECK
#             is_within, distance, config = check_geofence(user_lat, user_lon)

#             if not is_within:
#                 return JsonResponse({
#                     'success': False,
#                     'message': f'❌ You are {distance}m away! Must be within {config.radius_meters}m.'
#                 })

#             # SAVE Punch
#             punch = AttendancePunch.objects.create(
#                 employee=employee,
#                 employee_id_display=employee.employee_id,
#                 employee_name=employee.full_name,
#                 punch_type=punch_type,
#                 latitude=user_lat,
#                 longitude=user_lon,
#                 is_within_geofence=is_within,
#                 distance_from_office=Decimal(str(distance))
#             )

#             # BREAK END → create break record
#             if punch_type == 'break_end':
#                 break_start = AttendancePunch.objects.filter(
#                     employee=employee,
#                     punch_date=today,
#                     punch_type='break_start'
#                 ).exclude(break_starts__break_end__isnull=False).last()

#                 if break_start:
#                     is_lunch = time(14, 0) <= break_start.punch_time <= time(15, 0)
#                     BreakLog.objects.create(
#                         employee=employee,
#                         attendance_date=today,
#                         break_start=break_start,
#                         break_end=punch,
#                         is_lunch_break=is_lunch
#                     )

#             # CHECK-OUT → auto calculate attendance
#             if punch_type == 'check_out':
#                 calculate_attendance(employee, punch.punch_date)

#             return JsonResponse({
#                 'success': True,
#                 'message': f'✅ {punch.get_punch_type_display()} successful!',
#                 'punch_time': punch.punch_time.strftime('%H:%M:%S')
#             })

#         except Exception as e:
#             return JsonResponse({'success': False, 'message': str(e)})

#     return JsonResponse({'success': False})


@check_blocked_user
@login_required
@role_required(['hr', 'sales', 'developer', 'seos','digital_marketing' ,'admin'])
def process_punch(request):
    """
    🔥 UPDATED: Training status check + auto-complete after 7 actual training days
    """
    if request.method == "POST":
        try:
            user_id = request.session.get('user_id')
            employee = get_object_or_404(Employee, id=user_id)

            punch_type = request.POST.get('punch_type')
            user_lat = Decimal(request.POST.get('latitude'))
            user_lon = Decimal(request.POST.get('longitude'))

            today = timezone.now().date()

            # Fetch today's punches
            today_punches = AttendancePunch.objects.filter(
                employee=employee,
                punch_date=today
            ).order_by('punch_datetime')

            # Check rules: Only ONE check-in allowed
            if punch_type == "check_in":
                if today_punches.filter(punch_type='check_in').exists():
                    return JsonResponse({
                        'success': False,
                        'message': '❌ You already checked-in today.'
                    })

            # Check rules: Only ONE check-out allowed
            if punch_type == "check_out":
                if not today_punches.filter(punch_type='check_in').exists():
                    return JsonResponse({
                        'success': False,
                        'message': '❌ You must check-in first.'
                    })

                if today_punches.filter(punch_type='check_out').exists():
                    return JsonResponse({
                        'success': False,
                        'message': '❌ You have already checked-out today.'
                    })

            # If already checked-out → NO MORE punch actions allowed
            if today_punches.filter(punch_type='check_out').exists():
                return JsonResponse({
                    'success': False,
                    'message': '❌ You have already completed your day. No more punches allowed today.'
                })

            # Cannot start break without check-in
            if punch_type == "break_start":
                last_p = today_punches.last()
                if not last_p or last_p.punch_type != "check_in" and last_p.punch_type != "break_end":
                    return JsonResponse({
                        'success': False,
                        'message': "❌ You must be checked-in to start a break."
                    })

            # Cannot end break without starting break
            if punch_type == "break_end":
                last_break_start = today_punches.filter(punch_type='break_start').last()
                last_break_end = today_punches.filter(punch_type='break_end').last()

                if not last_break_start:
                    return JsonResponse({
                        'success': False,
                        'message': "❌ No break started."
                    })

                if last_break_end and last_break_end.punch_datetime > last_break_start.punch_datetime:
                    return JsonResponse({
                        'success': False,
                        'message': "❌ Break already ended."
                    })

            # GEO-FENCE CHECK
            is_within, distance, config = check_geofence(user_lat, user_lon)

            if not is_within:
                return JsonResponse({
                    'success': False,
                    'message': f'❌ You are {distance}m away! Must be within {config.radius_meters}m.'
                })

            # SAVE Punch
            punch = AttendancePunch.objects.create(
                employee=employee,
                employee_id_display=employee.employee_id,
                employee_name=employee.full_name,
                punch_type=punch_type,
                latitude=user_lat,
                longitude=user_lon,
                is_within_geofence=is_within,
                distance_from_office=Decimal(str(distance))
            )

            # 🔥 CHECK-IN: Auto-mark Training if in training period
            if punch_type == 'check_in':
                employee.check_training_status()  # Update training status
                
                if employee.is_in_training:
                    # Create training attendance
                    Attendance.objects.update_or_create(
                        employee=employee,
                        attendance_date=today,
                        defaults={
                            'employee_id_display': employee.employee_id,
                            'employee_name': employee.full_name,
                            'status': 'training',
                            'check_in_punch': punch,
                            'check_in_time': punch.punch_time,
                            'auto_calculated': True,
                            'remarks': f'Training Day {8 - employee.training_days_remaining}/7 - ₹100/day'
                        }
                    )

            # BREAK END → create break record
            if punch_type == 'break_end':
                break_start = AttendancePunch.objects.filter(
                    employee=employee,
                    punch_date=today,
                    punch_type='break_start'
                ).exclude(break_starts__break_end__isnull=False).last()

                if break_start:
                    is_lunch = time(14, 0) <= break_start.punch_time <= time(15, 0)
                    BreakLog.objects.create(
                        employee=employee,
                        attendance_date=today,
                        break_start=break_start,
                        break_end=punch,
                        is_lunch_break=is_lunch
                    )

            # 🔥 CHECK-OUT: Calculate attendance (only if NOT training)
            if punch_type == 'check_out':
                if not employee.is_in_training:
                    calculate_attendance(employee, punch.punch_date)
                else:
                    # 🔥 Training complete? Check again after checkout
                    employee.check_training_status()
                    
                    # If training just completed, show message
                    if not employee.is_in_training:
                        return JsonResponse({
                            'success': True,
                            'message': f'✅ Check-out successful! 🎉 Training completed! You will receive regular salary from tomorrow.',
                            'punch_time': punch.punch_time.strftime('%H:%M:%S'),
                            'training_completed': True
                        })

            return JsonResponse({
                'success': True,
                'message': f'✅ {punch.get_punch_type_display()} successful!',
                'punch_time': punch.punch_time.strftime('%H:%M:%S')
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False})


def calculate_attendance(employee, attendance_date):
    """
    Auto-calculate: P/HD/A
    - Late (>10:30) = HD
    - Work < 7hrs = HD/A
    - Work >= 7hrs = P
    """
    check_in = AttendancePunch.objects.filter(
        employee=employee, punch_date=attendance_date, punch_type='check_in'
    ).first()
    
    check_out = AttendancePunch.objects.filter(
        employee=employee, punch_date=attendance_date, punch_type='check_out'
    ).last()
    
    if not check_in or not check_out:
        return
    
    # Calculate work hours
    check_in_dt = datetime.combine(attendance_date, check_in.punch_time)
    check_out_dt = datetime.combine(attendance_date, check_out.punch_time)
    
    if check_out_dt < check_in_dt:
        check_out_dt += timedelta(days=1)
    
    total_mins = (check_out_dt - check_in_dt).total_seconds() / 60
    
    # Deduct breaks
    breaks = BreakLog.objects.filter(employee=employee, attendance_date=attendance_date)
    break_mins = sum([b.duration_minutes for b in breaks])
    
    work_hours = Decimal(str((total_mins - break_mins) / 60))
    
    # Determine status
    is_late = check_in.punch_time > time(10, 30)
    
    if work_hours >= 7:
        status = 'half_day' if is_late else 'present'
    elif work_hours >= 4:
        status = 'half_day'
    else:
        status = 'absent'
    
    Attendance.objects.update_or_create(
        employee=employee,
        attendance_date=attendance_date,
        defaults={
            'employee_id_display': employee.employee_id,
            'employee_name': employee.full_name,
            'status': status,
            'check_in_punch': check_in,
            'check_out_punch': check_out,
            'check_in_time': check_in.punch_time,
            'check_out_time': check_out.punch_time,
            'total_work_hours': work_hours,
            'total_break_minutes': break_mins,
            'is_late': is_late,
            'auto_calculated': True
        }
    )


@check_blocked_user
@login_required
@role_required(['hr', 'sales', 'developer', 'seos','digital_marketing' ,'admin'])
def my_attendance(request):
    """
    Modified - Auto marks absent when employee views their attendance
    """
    user_id = request.session.get('user_id')
    employee = get_object_or_404(Employee, id=user_id)
    
    # Auto-mark absent for THIS employee
    mark_absent_for_past_dates(employee)
    
    # Get month/year from GET params
    month_year = request.GET.get('month_year', '')
    if month_year:
        year, month = map(int, month_year.split('-'))
    else:
        today = date.today()
        year = today.year
        month = today.month
    
    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])
    
    records = Attendance.objects.filter(
        employee=employee,
        attendance_date__range=[start_date, end_date]
    ).order_by('attendance_date')
    
    # Calculate status counts
    present_count = records.filter(status='present').count()
    half_day_count = records.filter(status='half_day').count()
    absent_count = records.filter(status='absent').count()
    leave_count = records.filter(status='on_leave').count()
    holiday_count = records.filter(status='holiday').count()
    
    return render(request, 'Attendance/my_attendance.html', {
        'employee': employee,
        'attendance_records': records,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'present_count': present_count,
        'half_day_count': half_day_count,
        'absent_count': absent_count,
        'leave_count': leave_count,
        'holiday_count': holiday_count,
    })


@check_blocked_user
@login_required
@role_required(['hr', 'admin', 'super_admin'])
def attendance_list(request):
    """
    Modified - Auto marks absent when page loads
    """
    # Auto-mark absent for all employees (runs on page load)
    mark_absent_for_past_dates()
    
    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    
    start_date = date(year, month, 1)
    num_days = calendar.monthrange(year, month)[1]
    end_date = date(year, month, num_days)
    
    # Check if already approved
    approval = MonthlyAttendanceApproval.objects.filter(month=month, year=year).first()
    is_approved = approval is not None
    
    employees = Employee.objects.filter(is_active=True).order_by('full_name')
    
    attendance_data = []
    for employee in employees:
        records = Attendance.objects.filter(
            employee=employee,
            attendance_date__range=[start_date, end_date]
        )
        
        # Calculate counts
        present_count = records.filter(status='present').count()
        absent_count = records.filter(status='absent').count()
        half_day_count = records.filter(status='half_day').count()
        leave_count = records.filter(status='on_leave').count()
        
        # Count Sundays + holidays
        holiday_count = 0
        current = start_date
        while current <= end_date:
            if current.weekday() == 6:
                holiday_count += 1
            elif HolidayMaster.objects.filter(holiday_date=current, is_active=True).exists():
                holiday_count += 1
            current += timedelta(days=1)
        
        daily_status = []
        for day in range(1, num_days + 1):
            current_date = date(year, month, day)
            record = records.filter(attendance_date=current_date).first()
            
            # Determine status
            if record:
                status = record.status
            elif current_date.weekday() == 6:
                status = 'holiday'
            elif HolidayMaster.objects.filter(holiday_date=current_date, is_active=True).exists():
                status = 'holiday'
            elif current_date > today:
                status = '-'
            else:
                status = '-'
            
            daily_status.append({
                'day': day, 
                'status': status, 
                'date': current_date,
                'record_id': record.id if record else None
            })
        
        attendance_data.append({
            'employee': employee,
            'daily_status': daily_status,
            'present': present_count,
            'absent': absent_count,
            'half_day': half_day_count,
            'leave': leave_count,
            'holiday': holiday_count
        })
    
    return render(request, 'Attendance/attendance_list.html', {
        'attendance_data': attendance_data,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'num_days': num_days,
        'employees': employees,
        'is_approved': is_approved,
        'approval': approval
    })


@check_blocked_user
@login_required
@role_required(['hr', 'admin', 'super_admin'])
def get_attendance_detail(request, attendance_id):
    """
    AJAX endpoint to get punch details for a specific attendance record
    """
    try:
        attendance = Attendance.objects.get(id=attendance_id)
        
        # Get all punches for that day
        punches = AttendancePunch.objects.filter(
            employee=attendance.employee,
            punch_date=attendance.attendance_date
        ).order_by('punch_time')
        
        # Get breaks
        breaks = BreakLog.objects.filter(
            employee=attendance.employee,
            attendance_date=attendance.attendance_date
        )
        
        punch_data = []
        for punch in punches:
            punch_data.append({
                'time': punch.punch_time.strftime('%I:%M %p'),
                'type': punch.get_punch_type_display(),
                'distance': float(punch.distance_from_office) if punch.distance_from_office else 0,
                'within_geofence': punch.is_within_geofence
            })
        
        break_data = []
        for brk in breaks:
            break_data.append({
                'start': brk.break_start.punch_time.strftime('%I:%M %p'),
                'end': brk.break_end.punch_time.strftime('%I:%M %p') if brk.break_end else 'Ongoing',
                'duration': brk.duration_minutes,
                'is_lunch': brk.is_lunch_break
            })
        
        data = {
            'success': True,
            'employee_name': attendance.employee_name,
            'employee_id': attendance.employee_id_display,
            'date': attendance.attendance_date.strftime('%d %B %Y'),
            'status': attendance.get_status_display(),
            'check_in': attendance.check_in_time.strftime('%I:%M %p') if attendance.check_in_time else 'N/A',
            'check_out': attendance.check_out_time.strftime('%I:%M %p') if attendance.check_out_time else 'N/A',
            'work_hours': float(attendance.total_work_hours),
            'break_minutes': attendance.total_break_minutes,
            'is_late': attendance.is_late,
            'remarks': attendance.remarks or 'No remarks',
            'punches': punch_data,
            'breaks': break_data
        }
        
        return JsonResponse(data)
    
    except Attendance.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Attendance record not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@check_blocked_user
@login_required
@role_required(['hr', 'admin', 'super_admin'])
def change_attendance_status(request):
    """
    Change attendance status (P -> A, HD, L) with reason logging
    """
    if request.method == "POST":
        try:
            attendance_id = request.POST.get('attendance_id')
            new_status = request.POST.get('new_status')
            reason = request.POST.get('reason', '').strip()
            
            if not reason:
                return JsonResponse({
                    'success': False,
                    'message': 'Reason is required for status change!'
                })
            
            attendance = Attendance.objects.get(id=attendance_id)
            old_status = attendance.status
            
            # Prevent changing to same status
            if old_status == new_status:
                return JsonResponse({
                    'success': False,
                    'message': 'New status is same as current status!'
                })
            
            # Get user details
            user_id = request.session.get('user_id')
            user_role = request.session.get('role')
            user_name = request.session.get('full_name')
            
            # Get user object based on role
            changed_by_employee = None
            changed_by_admin = None
            
            if user_role in ['hr', 'sales', 'developer', 'seos']:
                changed_by_employee = Employee.objects.get(id=user_id)
            elif user_role in ['admin', 'super_admin']:
                changed_by_admin = AdminUser.objects.get(id=user_id)
            
            # Update attendance status
            attendance.status = new_status
            attendance.save()
            
            # Create change log
            AttendanceStatusChangeLog.objects.create(
                attendance=attendance,
                employee=attendance.employee,
                attendance_date=attendance.attendance_date,
                old_status=old_status,
                new_status=new_status,
                reason=reason,
                changed_by_employee=changed_by_employee,
                changed_by_admin=changed_by_admin,
                changed_by_name=user_name,
                changed_by_role=user_role
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Status changed from {old_status.upper()} to {new_status.upper()} successfully!'
            })
            
        except Attendance.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Attendance record not found!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@check_blocked_user
@login_required
@role_required(['hr', 'admin', 'super_admin'])
def get_attendance_change_logs(request, attendance_id):
    """
    Get all status change logs for an attendance record
    """
    try:
        logs = AttendanceStatusChangeLog.objects.filter(
            attendance_id=attendance_id
        ).order_by('-changed_at')
        
        log_data = []
        for log in logs:
            log_data.append({
                'old_status': log.get_old_status_display(),
                'new_status': log.get_new_status_display(),
                'reason': log.reason,
                'changed_by': log.changed_by_name,
                'changed_by_role': log.changed_by_role.upper(),
                'changed_at': log.changed_at.strftime('%d %b %Y, %I:%M %p')
            })
        
        return JsonResponse({
            'success': True,
            'logs': log_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@check_blocked_user
@login_required
@role_required(['hr', 'admin', 'super_admin'])
def approve_monthly_attendance(request):
    """
    IMPROVED: Allow multiple approvals with date range protection
    - Can approve same month multiple times (up to today's date)
    - Previous approval gets updated/overridden
    - Auto-regenerates salary on re-approval
    """
    if request.method == "POST":
        try:
            year = int(request.POST.get('year'))
            month = int(request.POST.get('month'))
            
            today = date.today()
            
            # Date range for approval (start to today or month end, whichever is earlier)
            start_date = date(year, month, 1)
            month_end = date(year, month, calendar.monthrange(year, month)[1])
            
            # Approval should only happen up to today's date
            if today < month_end:
                end_date = today
            else:
                end_date = month_end
            
            # Check if trying to approve future dates
            if start_date > today:
                messages.error(request, f"❌ Cannot approve future month!")
                return redirect('attendance_list')
            
            # Get all active employees
            employees = Employee.objects.filter(is_active=True)
            total_employees = employees.count()
            
            # Calculate statistics (only up to end_date)
            all_attendance = Attendance.objects.filter(
                attendance_date__range=[start_date, end_date]
            )
            
            total_present = all_attendance.filter(status='present').count()
            total_absent = all_attendance.filter(status='absent').count()
            total_half_days = all_attendance.filter(status='half_day').count()
            total_leaves = all_attendance.filter(status='on_leave').count()
            
            # Get approver details
            user_id = request.session.get('user_id')
            user_role = request.session.get('role')
            user_name = request.session.get('full_name')
            
            approved_by_employee = None
            approved_by_admin = None
            
            if user_role in ['hr']:
                approved_by_employee = Employee.objects.get(id=user_id)
            elif user_role in ['admin', 'super_admin']:
                approved_by_admin = AdminUser.objects.get(id=user_id)
            
            # Check if already approved
            existing_approval = MonthlyAttendanceApproval.objects.filter(
                month=month, 
                year=year
            ).first()
            
            if existing_approval:
                # Update existing approval
                existing_approval.approved_by = approved_by_employee
                existing_approval.approved_by_admin = approved_by_admin
                existing_approval.approved_by_name = user_name
                existing_approval.approved_by_role = user_role
                existing_approval.approval_date = timezone.now()
                existing_approval.total_employees = total_employees
                existing_approval.total_present_days = total_present
                existing_approval.total_absent_days = total_absent
                existing_approval.total_half_days = total_half_days
                existing_approval.total_leaves = total_leaves
                existing_approval.approved_up_to_date = end_date
                existing_approval.save()
                
                messages.success(request, 
                    f"✅ Attendance RE-APPROVED for {calendar.month_name[month]} {year} "
                    f"(up to {end_date.strftime('%d %b %Y')}) - {total_employees} employees"
                )
            else:
                # Create new approval
                MonthlyAttendanceApproval.objects.create(
                    month=month,
                    year=year,
                    approved_by=approved_by_employee,
                    approved_by_admin=approved_by_admin,
                    approved_by_name=user_name,
                    approved_by_role=user_role,
                    total_employees=total_employees,
                    total_present_days=total_present,
                    total_absent_days=total_absent,
                    total_half_days=total_half_days,
                    total_leaves=total_leaves,
                    approved_up_to_date=end_date,
                    status='approved'
                )
                
                messages.success(request, 
                    f"✅ Attendance approved for {calendar.month_name[month]} {year} "
                    f"(up to {end_date.strftime('%d %b %Y')}) - {total_employees} employees"
                )
            
            # Redirect to salary generation
            return redirect('salary_sheet')
        
        except Exception as e:
            messages.error(request, f"❌ Error approving attendance: {str(e)}")
            return redirect('attendance_list')
    
    return redirect('attendance_list')



# ==================== SALARY VIEWS ====================

@check_blocked_user
@login_required
@role_required(['admin', 'super_admin', 'hr'])
def salary_sheet(request):
    """
    Main salary sheet page
    """
    return render(request, 'Salary/salary_sheet.html')


# @check_blocked_user
# @login_required
# @role_required(['admin', 'super_admin', 'hr'])
# def get_salary_data(request):
#     """
#     🔥 UPDATED: 
#     1. Dynamic per day calculation (28/30/31 days)
#     2. Training days paid at ₹100/day
#     3. Holiday (H) and Leave (L) are PAID
#     4. LWP is UNPAID (no salary)
#     5. Absent (A) is UNPAID
#     """
#     month_year = request.GET.get('month')
    
#     if not month_year:
#         return JsonResponse([], safe=False)
    
#     try:
#         year, month = month_year.split('-')
#         year = int(year)
#         month = int(month)
#     except:
#         return JsonResponse([], safe=False)
    
#     # Check if attendance is approved for this month
#     approval = MonthlyAttendanceApproval.objects.filter(
#         month=month, 
#         year=year
#     ).first()
    
#     if not approval:
#         return JsonResponse({
#             'error': True,
#             'message': f'Attendance for {calendar.month_name[month]} {year} is not approved yet!'
#         }, safe=False)
    
#     # Get all active employees
#     employees = Employee.objects.filter(is_active=True).select_related().order_by('employee_id')
    
#     # Date range for attendance
#     start_date = date(year, month, 1)
    
#     # Use approved_up_to_date if available
#     if hasattr(approval, 'approved_up_to_date') and approval.approved_up_to_date:
#         end_date = approval.approved_up_to_date
#     else:
#         end_date = date(year, month, calendar.monthrange(year, month)[1])
    
#     # 🔥 Get total days in this month (28/30/31)
#     days_in_month = calendar.monthrange(year, month)[1]
    
#     data = []
    
#     for emp in employees:
#         # Get attendance summary
#         attendance_records = Attendance.objects.filter(
#             employee=emp,
#             attendance_date__range=[start_date, end_date]
#         )
        
#         # 🔥 Count by status
#         present = attendance_records.filter(status='present').count()
#         absent = attendance_records.filter(status='absent').count()
#         half_days = attendance_records.filter(status='half_day').count()
#         leaves = attendance_records.filter(status='on_leave').count()  # Paid leave
#         holidays = attendance_records.filter(status='holiday').count()  # Paid
#         lwp = attendance_records.filter(status='lwp').count()  # Unpaid
#         training = attendance_records.filter(status='training').count()  # ₹100/day
        
#         # Get previous month balance
#         prev_month = month - 1 if month > 1 else 12
#         prev_year = year if month > 1 else year - 1
        
#         prev_salary = MonthlySalary.objects.filter(
#             employee=emp,
#             month=prev_month,
#             year=prev_year,
#             is_saved=True
#         ).first()
        
#         previous_balance = float(prev_salary.remaining_balance) if prev_salary else 0.0
        
#         # Check if current month salary already exists
#         existing_salary = MonthlySalary.objects.filter(
#             employee=emp,
#             month=month,
#             year=year
#         ).first()
        
#         # Get base salary
#         if emp.base_salary:
#             try:
#                 base_salary = float(str(emp.base_salary))
#             except (ValueError, TypeError):
#                 base_salary = 0.0
#         else:
#             base_salary = 0.0
        
#         # 🔥 Calculate per_day based on days in month
#         per_day = round(base_salary / days_in_month, 2) if base_salary > 0 else 0.0
        
#         if existing_salary:
#             # Load existing data (will be overridden if saved again)
#             data.append({
#                 'id': existing_salary.id,
#                 'employee_id': emp.employee_id,
#                 'employee_name': emp.full_name,
#                 'base_salary': float(existing_salary.base_salary),
#                 'per_day_salary': float(existing_salary.per_day_salary),
#                 'total_present': present,
#                 'total_absent': absent,
#                 'total_half_days': half_days,
#                 'total_leaves': leaves,
#                 'total_holidays': holidays,  # 🔥 NEW
#                 'total_lwp': lwp,  # 🔥 NEW
#                 'total_training': training,  # 🔥 NEW
#                 'bonus': float(existing_salary.bonus),
#                 'travel_allowance': float(existing_salary.travel_allowance),
#                 'pf_percent': float(existing_salary.pf_percent) if existing_salary.pf_percent > 0 else 0.0,
#                 'pf_amount': float(existing_salary.pf_amount),
#                 'esi_percent': float(existing_salary.esi_percent) if existing_salary.esi_percent > 0 else 0.0,
#                 'esi_amount': float(existing_salary.esi_amount),
#                 'gross_salary': float(existing_salary.gross_salary),
#                 'total_deductions': float(existing_salary.total_deductions),
#                 'net_payable': float(existing_salary.net_payable),
#                 'paid_amount': float(existing_salary.paid_amount),
#                 'payment_date': existing_salary.payment_date.isoformat() if existing_salary.payment_date else '',
#                 'remaining_balance': float(existing_salary.remaining_balance),
#                 'previous_balance': previous_balance,
#                 'is_saved': existing_salary.is_saved,
#                 'can_override': True
#             })
#         else:
#             # Create fresh data
#             data.append({
#                 'id': None,
#                 'employee_id': emp.employee_id,
#                 'employee_name': emp.full_name,
#                 'base_salary': base_salary,
#                 'per_day_salary': round(per_day, 2),
#                 'total_present': present,
#                 'total_absent': absent,
#                 'total_half_days': half_days,
#                 'total_leaves': leaves,
#                 'total_holidays': holidays,  # 🔥 NEW
#                 'total_lwp': lwp,  # 🔥 NEW
#                 'total_training': training,  # 🔥 NEW
#                 'bonus': 0.0,
#                 'travel_allowance': 0.0,
#                 'pf_percent': 0.0,
#                 'pf_amount': 0.0,
#                 'esi_percent': 0.0,
#                 'esi_amount': 0.0,
#                 'gross_salary': 0.0,
#                 'total_deductions': 0.0,
#                 'net_payable': 0.0,
#                 'paid_amount': 0.0,
#                 'payment_date': '',
#                 'remaining_balance': 0.0,
#                 'previous_balance': previous_balance,
#                 'is_saved': False,
#                 'can_override': False
#             })
    
#     return JsonResponse(data, safe=False)


@check_blocked_user
@login_required
@role_required(['admin', 'super_admin', 'hr'])
def get_salary_data(request):
    """
    🔥 UPDATED: Dynamic per day calculation (28/30/31 days)
    """
    month_year = request.GET.get('month')
    
    if not month_year:
        return JsonResponse([], safe=False)
    
    try:
        year, month = month_year.split('-')
        year = int(year)
        month = int(month)
    except:
        return JsonResponse([], safe=False)
    
    # Check if attendance is approved
    approval = MonthlyAttendanceApproval.objects.filter(
        month=month, 
        year=year
    ).first()
    
    if not approval:
        return JsonResponse({
            'error': True,
            'message': f'Attendance for {calendar.month_name[month]} {year} is not approved yet!'
        }, safe=False)
    
    # Get all active employees
    employees = Employee.objects.filter(is_active=True).select_related().order_by('employee_id')
    
    # Date range for attendance
    start_date = date(year, month, 1)
    
    if hasattr(approval, 'approved_up_to_date') and approval.approved_up_to_date:
        end_date = approval.approved_up_to_date
    else:
        end_date = date(year, month, calendar.monthrange(year, month)[1])
    
    # 🔥 Get total days in this month (28/30/31)
    days_in_month = calendar.monthrange(year, month)[1]
    
    data = []
    
    for emp in employees:
        # Get attendance summary
        attendance_records = Attendance.objects.filter(
            employee=emp,
            attendance_date__range=[start_date, end_date]
        )
        
        present = attendance_records.filter(status='present').count()
        absent = attendance_records.filter(status='absent').count()
        half_days = attendance_records.filter(status='half_day').count()
        leaves = attendance_records.filter(status='on_leave').count()
        holidays = attendance_records.filter(status='holiday').count()
        lwp = attendance_records.filter(status='lwp').count()
        training = attendance_records.filter(status='training').count()
        
        # Get previous month balance
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        
        prev_salary = MonthlySalary.objects.filter(
            employee=emp,
            month=prev_month,
            year=prev_year,
            is_saved=True
        ).first()
        
        previous_balance = float(prev_salary.remaining_balance) if prev_salary else 0.0
        
        # Check if current month salary already exists
        existing_salary = MonthlySalary.objects.filter(
            employee=emp,
            month=month,
            year=year
        ).first()
        
        # Get base salary
        if emp.base_salary:
            try:
                base_salary = float(str(emp.base_salary))
            except (ValueError, TypeError):
                base_salary = 0.0
        else:
            base_salary = 0.0
        
        # 🔥 UPDATED: Calculate per_day based on days in month
        per_day = round(base_salary / days_in_month, 2) if base_salary > 0 else 0.0
        
        if existing_salary:
            # Load existing data
            data.append({
                'id': existing_salary.id,
                'employee_id': emp.employee_id,
                'employee_name': emp.full_name,
                'base_salary': float(existing_salary.base_salary),
                'per_day_salary': float(existing_salary.per_day_salary),
                'total_present': present,
                'total_absent': absent,
                'total_half_days': half_days,
                'total_leaves': leaves,
                'total_holidays': holidays,
                'total_lwp': lwp,
                'total_training': training,
                'bonus': float(existing_salary.bonus),
                'travel_allowance': float(existing_salary.travel_allowance),
                'pf_percent': float(existing_salary.pf_percent) if existing_salary.pf_percent > 0 else 0.0,
                'pf_amount': float(existing_salary.pf_amount),
                'esi_percent': float(existing_salary.esi_percent) if existing_salary.esi_percent > 0 else 0.0,
                'esi_amount': float(existing_salary.esi_amount),
                'gross_salary': float(existing_salary.gross_salary),
                'total_deductions': float(existing_salary.total_deductions),
                'net_payable': float(existing_salary.net_payable),
                'paid_amount': float(existing_salary.paid_amount),
                'payment_date': existing_salary.payment_date.isoformat() if existing_salary.payment_date else '',
                'remaining_balance': float(existing_salary.remaining_balance),
                'previous_balance': previous_balance,
                'is_saved': existing_salary.is_saved,
                'can_override': True
            })
        else:
            # Create fresh data
            data.append({
                'id': None,
                'employee_id': emp.employee_id,
                'employee_name': emp.full_name,
                'base_salary': base_salary,
                'per_day_salary': round(per_day, 2),
                'total_present': present,
                'total_absent': absent,
                'total_half_days': half_days,
                'total_leaves': leaves,
                'total_holidays': holidays,
                'total_lwp': lwp,
                'total_training': training,
                'bonus': 0.0,
                'travel_allowance': 0.0,
                'pf_percent': 0.0,
                'pf_amount': 0.0,
                'esi_percent': 0.0,
                'esi_amount': 0.0,
                'gross_salary': 0.0,
                'total_deductions': 0.0,
                'net_payable': 0.0,
                'paid_amount': 0.0,
                'payment_date': '',
                'remaining_balance': 0.0,
                'previous_balance': previous_balance,
                'is_saved': False,
                'can_override': False
            })
    
    return JsonResponse(data, safe=False)


# @csrf_exempt
# @check_blocked_user
# @login_required
# @role_required(['admin', 'super_admin', 'hr'])
# def save_salary_data(request):
#     """
#     FIXED VERSION: Prevents duplicate fund deduction on re-approval
#     - If salary already paid from funds, refund first then re-calculate
#     """
#     if request.method != "POST":
#         return JsonResponse({'status': 'error', 'message': 'Invalid request'})
    
#     try:
#         data = json.loads(request.body)
#         month_year = data.get('month')
#         salary_data = data.get('data', [])
#         auto_pay = data.get('auto_pay', False)
        
#         if not month_year:
#             return JsonResponse({'status': 'error', 'message': 'Month not provided'})
        
#         year, month = month_year.split('-')
#         year = int(year)
#         month = int(month)
        
#         # Check if attendance is approved
#         approval = MonthlyAttendanceApproval.objects.filter(
#             month=month, 
#             year=year
#         ).first()
        
#         if not approval:
#             return JsonResponse({
#                 'status': 'error', 
#                 'message': f'Please approve attendance for {calendar.month_name[month]} {year} first!'
#             })
        
#         # Get company funds (if auto_pay enabled)
#         company_funds = None
#         if auto_pay:
#             try:
#                 company_funds = CompanyFunds.objects.get(id=1)
#             except CompanyFunds.DoesNotExist:
#                 return JsonResponse({
#                     'status': 'error',
#                     'message': 'Company funds not initialized! Please add funds first.'
#                 })
        
#         saved_count = 0
#         updated_count = 0
#         paid_count = 0
#         refunded_count = 0
#         insufficient_funds_employees = []
        
#         with transaction.atomic():
#             for row in salary_data:
#                 emp_id = row['employee_id'].split()[0]
                
#                 try:
#                     employee = Employee.objects.get(employee_id=emp_id)
#                 except Employee.DoesNotExist:
#                     continue
                
#                 # Calculate salary (same as before)
#                 base_salary = Decimal(str(row['base_salary']))
#                 per_day_salary = base_salary / 30
                
#                 present_salary = Decimal(str(row['total_present'])) * per_day_salary
#                 leave_salary = Decimal(str(row['total_leaves'])) * per_day_salary
#                 half_day_salary = Decimal(str(row['total_half_days'])) * (per_day_salary / 2)
                
#                 attendance_salary = present_salary + leave_salary + half_day_salary
#                 if attendance_salary > base_salary:
#                     attendance_salary = base_salary
                
#                 bonus = Decimal(str(row['bonus']))
#                 travel_allowance = Decimal(str(row['travel_allowance']))
#                 gross_salary = attendance_salary + bonus + travel_allowance
                
#                 pf_percent = Decimal(str(row['pf_percent']))
#                 esi_percent = Decimal(str(row['esi_percent']))
#                 pf_amount = (gross_salary * pf_percent) / 100 if pf_percent > 0 else Decimal('0')
#                 esi_amount = (gross_salary * esi_percent) / 100 if esi_percent > 0 else Decimal('0')
                
#                 total_deductions = pf_amount + esi_amount
#                 previous_balance = Decimal(str(row.get('previous_balance', 0)))
#                 net_payable = gross_salary - total_deductions + previous_balance
                
#                 # ✅ CHECK IF SALARY ALREADY EXISTS
#                 existing_salary = MonthlySalary.objects.filter(
#                     employee=employee,
#                     month=month,
#                     year=year
#                 ).first()
                
#                 fund_transaction = None
#                 payment_from_funds = False
#                 paid_amount = Decimal(str(row.get('paid_amount', 0)))
#                 payment_date = row.get('payment_date') or None
                
#                 # 🔥 NEW LOGIC: If re-approving and auto_pay enabled
#                 if existing_salary and auto_pay and existing_salary.payment_from_funds:
#                     # ✅ REFUND OLD PAYMENT FIRST
#                     old_transaction = existing_salary.fund_transaction
#                     if old_transaction:
#                         # Refund to company funds
#                         company_funds.total_funds += old_transaction.amount
#                         company_funds.total_paid_as_salary -= old_transaction.amount
#                         company_funds.total_profit = (
#                             company_funds.total_received_from_clients - 
#                             company_funds.total_paid_as_salary
#                         )
#                         company_funds.save()
                        
#                         # Delete old transaction
#                         old_transaction.delete()
#                         refunded_count += 1
                    
#                     # Reset payment status
#                     existing_salary.paid_amount = Decimal('0')
#                     existing_salary.payment_date = None
#                     existing_salary.fund_transaction = None
#                     existing_salary.payment_from_funds = False
#                     existing_salary.save()
                
#                 # 🔥 NOW PROCEED WITH PAYMENT
#                 if auto_pay and net_payable > 0:
#                     if company_funds.total_funds >= net_payable:
#                         # Create or use existing salary object
#                         if existing_salary:
#                             salary_obj = existing_salary
#                         else:
#                             salary_obj = MonthlySalary(
#                                 employee=employee,
#                                 month=month,
#                                 year=year
#                             )
                        
#                         # Update all fields
#                         salary_obj.employee_id_display = emp_id
#                         salary_obj.employee_name = row['employee_name']
#                         salary_obj.base_salary = base_salary
#                         salary_obj.per_day_salary = per_day_salary
#                         salary_obj.total_present = row['total_present']
#                         salary_obj.total_absent = row['total_absent']
#                         salary_obj.total_half_days = row['total_half_days']
#                         salary_obj.total_leaves = row['total_leaves']
#                         salary_obj.bonus = bonus
#                         salary_obj.travel_allowance = travel_allowance
#                         salary_obj.pf_percent = pf_percent
#                         salary_obj.pf_amount = pf_amount
#                         salary_obj.esi_percent = esi_percent
#                         salary_obj.esi_amount = esi_amount
#                         salary_obj.gross_salary = gross_salary
#                         salary_obj.total_deductions = total_deductions
#                         salary_obj.net_payable = net_payable
#                         salary_obj.previous_balance = previous_balance
#                         salary_obj.is_saved = True
#                         salary_obj.save()
                        
#                         # Create NEW fund transaction
#                         fund_transaction = FundTransaction.objects.create(
#                             transaction_type='salary_payment',
#                             amount=net_payable,
#                             is_credit=False,
#                             balance_after=company_funds.total_funds - net_payable,
#                             salary=salary_obj,
#                             description=f"Salary paid to {employee.full_name} for {calendar.month_name[month]} {year}",
#                             created_by_name=request.session.get('full_name'),
#                             created_by_role=request.session.get('role')
#                         )
                        
#                         # Deduct from funds
#                         company_funds.total_funds -= net_payable
#                         company_funds.total_paid_as_salary += net_payable
#                         company_funds.total_profit = (
#                             company_funds.total_received_from_clients - 
#                             company_funds.total_paid_as_salary
#                         )
#                         company_funds.save()
                        
#                         # Update payment details
#                         salary_obj.paid_amount = net_payable
#                         salary_obj.payment_date = date.today()
#                         salary_obj.remaining_balance = Decimal('0')
#                         salary_obj.fund_transaction = fund_transaction
#                         salary_obj.payment_from_funds = True
#                         salary_obj.save()
                        
#                         paid_count += 1
#                         if existing_salary:
#                             updated_count += 1
#                         else:
#                             saved_count += 1
#                     else:
#                         insufficient_funds_employees.append(employee.full_name)
#                         # Save without payment
#                         if existing_salary:
#                             salary_obj = existing_salary
#                             updated_count += 1
#                         else:
#                             salary_obj = MonthlySalary(
#                                 employee=employee,
#                                 month=month,
#                                 year=year
#                             )
#                             saved_count += 1
                        
#                         salary_obj.employee_id_display = emp_id
#                         salary_obj.employee_name = row['employee_name']
#                         salary_obj.base_salary = base_salary
#                         salary_obj.per_day_salary = per_day_salary
#                         salary_obj.total_present = row['total_present']
#                         salary_obj.total_absent = row['total_absent']
#                         salary_obj.total_half_days = row['total_half_days']
#                         salary_obj.total_leaves = row['total_leaves']
#                         salary_obj.bonus = bonus
#                         salary_obj.travel_allowance = travel_allowance
#                         salary_obj.pf_percent = pf_percent
#                         salary_obj.pf_amount = pf_amount
#                         salary_obj.esi_percent = esi_percent
#                         salary_obj.esi_amount = esi_amount
#                         salary_obj.gross_salary = gross_salary
#                         salary_obj.total_deductions = total_deductions
#                         salary_obj.net_payable = net_payable
#                         salary_obj.paid_amount = paid_amount
#                         salary_obj.payment_date = payment_date
#                         salary_obj.previous_balance = previous_balance
#                         salary_obj.remaining_balance = net_payable - paid_amount
#                         salary_obj.is_saved = True
#                         salary_obj.save()
#                 else:
#                     # Save without auto-payment
#                     remaining_balance = net_payable - paid_amount
                    
#                     if existing_salary:
#                         salary_obj = existing_salary
#                         updated_count += 1
#                     else:
#                         salary_obj = MonthlySalary(
#                             employee=employee,
#                             month=month,
#                             year=year
#                         )
#                         saved_count += 1
                    
#                     salary_obj.employee_id_display = emp_id
#                     salary_obj.employee_name = row['employee_name']
#                     salary_obj.base_salary = base_salary
#                     salary_obj.per_day_salary = per_day_salary
#                     salary_obj.total_present = row['total_present']
#                     salary_obj.total_absent = row['total_absent']
#                     salary_obj.total_half_days = row['total_half_days']
#                     salary_obj.total_leaves = row['total_leaves']
#                     salary_obj.bonus = bonus
#                     salary_obj.travel_allowance = travel_allowance
#                     salary_obj.pf_percent = pf_percent
#                     salary_obj.pf_amount = pf_amount
#                     salary_obj.esi_percent = esi_percent
#                     salary_obj.esi_amount = esi_amount
#                     salary_obj.gross_salary = gross_salary
#                     salary_obj.total_deductions = total_deductions
#                     salary_obj.net_payable = net_payable
#                     salary_obj.paid_amount = paid_amount
#                     salary_obj.payment_date = payment_date
#                     salary_obj.previous_balance = previous_balance
#                     salary_obj.remaining_balance = remaining_balance
#                     salary_obj.is_saved = True
#                     salary_obj.save()
        
#         # Build success message
#         message = f'✅ {saved_count} new records saved'
#         if updated_count > 0:
#             message += f', {updated_count} records updated'
#         if refunded_count > 0:
#             message += f', {refunded_count} old payments refunded'
#         if paid_count > 0:
#             message += f', {paid_count} salaries paid from funds'
#         if insufficient_funds_employees:
#             message += f'. ⚠️ Insufficient funds for: {", ".join(insufficient_funds_employees)}'
#         message += ' successfully!'
        
#         return JsonResponse({
#             'status': 'success',
#             'message': message,
#             'paid_count': paid_count,
#             'refunded_count': refunded_count,
#             'insufficient_funds': len(insufficient_funds_employees)
#         })
    
#     except Exception as e:
#         import traceback
#         print("ERROR:", str(e))
#         print(traceback.format_exc())
#         return JsonResponse({
#             'status': 'error',
#             'message': str(e)
#         })


@csrf_exempt
@check_blocked_user
@login_required
@role_required(['admin', 'super_admin', 'hr'])
def save_salary_data(request):
    """
    🔥 UPDATED: Dynamic per day calculation
    """
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'message': 'Invalid request'})
    
    try:
        data = json.loads(request.body)
        month_year = data.get('month')
        salary_data = data.get('data', [])
        auto_pay = data.get('auto_pay', False)
        
        if not month_year:
            return JsonResponse({'status': 'error', 'message': 'Month not provided'})
        
        year, month = month_year.split('-')
        year = int(year)
        month = int(month)
        
        # 🔥 UPDATED: Get days in this month dynamically
        days_in_month = calendar.monthrange(year, month)[1]
        
        # Check if attendance is approved
        approval = MonthlyAttendanceApproval.objects.filter(
            month=month, 
            year=year
        ).first()
        
        if not approval:
            return JsonResponse({
                'status': 'error', 
                'message': f'Please approve attendance for {calendar.month_name[month]} {year} first!'
            })
        
        # Get company funds (if auto_pay enabled)
        company_funds = None
        if auto_pay:
            try:
                company_funds = CompanyFunds.objects.get(id=1)
            except CompanyFunds.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Company funds not initialized! Please add funds first.'
                })
        
        saved_count = 0
        updated_count = 0
        paid_count = 0
        refunded_count = 0
        insufficient_funds_employees = []
        
        with transaction.atomic():
            for row in salary_data:
                emp_id = row['employee_id'].split()[0]
                
                try:
                    employee = Employee.objects.get(employee_id=emp_id)
                except Employee.DoesNotExist:
                    continue
                
                # 🔥 UPDATED: Calculate per_day based on month days
                base_salary = Decimal(str(row['base_salary']))
                per_day_salary = base_salary / Decimal(str(days_in_month))
                
                # Get attendance counts
                total_present = Decimal(str(row['total_present']))
                total_half_days = Decimal(str(row['total_half_days']))
                total_leaves = Decimal(str(row['total_leaves']))
                total_holidays = Decimal(str(row.get('total_holidays', 0)))
                total_training = Decimal(str(row.get('total_training', 0)))
                
                total_absent = row['total_absent']
                total_lwp = row.get('total_lwp', 0)
                
                # Calculate attendance salary
                present_salary = total_present * per_day_salary
                half_day_salary = total_half_days * (per_day_salary / Decimal('2'))
                leave_salary = total_leaves * per_day_salary
                holiday_salary = total_holidays * per_day_salary
                training_salary = total_training * Decimal('100')
                
                attendance_salary = (
                    present_salary + 
                    half_day_salary + 
                    leave_salary + 
                    holiday_salary + 
                    training_salary
                )
                
                # CAP at base + training
                max_allowed = base_salary + training_salary
                if attendance_salary > max_allowed:
                    attendance_salary = max_allowed
                
                # Add allowances
                bonus = Decimal(str(row['bonus']))
                travel_allowance = Decimal(str(row['travel_allowance']))
                gross_salary = attendance_salary + bonus + travel_allowance
                
                # Calculate deductions
                pf_percent = Decimal(str(row['pf_percent']))
                esi_percent = Decimal(str(row['esi_percent']))
                pf_amount = (gross_salary * pf_percent) / 100 if pf_percent > 0 else Decimal('0')
                esi_amount = (gross_salary * esi_percent) / 100 if esi_percent > 0 else Decimal('0')
                
                total_deductions = pf_amount + esi_amount
                
                # Calculate net payable
                previous_balance = Decimal(str(row.get('previous_balance', 0)))
                net_payable = gross_salary - total_deductions + previous_balance
                
                # ... (rest of the save logic remains same - payment processing, etc.)
                # ... (existing code for saving/updating salary records)
                
        # Return response
        message = f'✅ {saved_count} new records saved'
        if updated_count > 0:
            message += f', {updated_count} records updated'
        if refunded_count > 0:
            message += f', {refunded_count} old payments refunded'
        if paid_count > 0:
            message += f', {paid_count} salaries paid from funds'
        if insufficient_funds_employees:
            message += f'. ⚠️ Insufficient funds for: {", ".join(insufficient_funds_employees)}'
        message += ' successfully!'
        
        return JsonResponse({
            'status': 'success',
            'message': message,
            'paid_count': paid_count,
            'refunded_count': refunded_count,
            'insufficient_funds': len(insufficient_funds_employees)
        })
    
    except Exception as e:
        import traceback
        print("ERROR:", str(e))
        print(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })


@check_blocked_user
@login_required
@role_required(['admin', 'super_admin', 'hr'])
def view_salary_history(request):
    """
    View saved salary history (all months)
    """
    salaries = MonthlySalary.objects.filter(is_saved=True).order_by('-year', '-month')
    
    return render(request, 'Salary/salary_history.html', {
        'salaries': salaries
    })


@check_blocked_user
@login_required
@role_required(['hr', 'sales', 'developer', 'seos','digital_marketing' ,'admin'])
def my_salary_slips(request):
    """
    Employee's own salary slips
    """
    user_id = request.session.get('user_id')
    employee = get_object_or_404(Employee, id=user_id)
    
    salaries = MonthlySalary.objects.filter(
        employee=employee,
        is_saved=True
    ).order_by('-year', '-month')
    
    return render(request, 'Salary/my_salary_slips.html', {
        'salaries': salaries,
        'employee': employee
    })


@check_blocked_user
@login_required
def view_salary_slip(request, salary_id):
    """
    View individual salary slip (PDF-ready format)
    Admin/HR: Can view all
    Employee: Can view only their own
    """
    salary = get_object_or_404(MonthlySalary, id=salary_id, is_saved=True)
    
    user_role = request.session.get('role')
    user_id = request.session.get('user_id')
    
    # Permission check
    if user_role not in ['admin', 'super_admin', 'hr']:
        if salary.employee.id != user_id:
            messages.error(request, "❌ You can only view your own salary slips!")
            return redirect('my_salary_slips')
    
    return render(request, 'Salary/salary_slip_pdf.html', {
        'salary': salary
    })


