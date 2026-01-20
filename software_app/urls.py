from django.urls import path
from software_app.views import*

urlpatterns = [

    path('',   login_view, name='login'),
    path('login/',   login_view, name='login'),
    path('logout/',   logout_view, name='logout'),
    path('dashboard/',   dashboard, name='dashboard'),
    path('my-profile/', my_profile, name='my_profile'),

    # Employee URLS
    # Employee Management
    path('add-employee/',   add_employee, name='add_employee'),
    path('employee-list/',   employee_list, name='employee_list'),
    path('edit-employee/<int:id>/',   edit_employee, name='edit_employee'),
    path('delete-employee/<int:id>/',   delete_employee, name='delete_employee'),
    
    # Document Management
    path('delete-employee-document/<int:id>/',   delete_employee_document, name='delete_employee_document'),
    
    # Status & Block Management
    path('toggle-employee-status/<int:id>/',   toggle_employee_status, name='toggle_employee_status'),
    path('toggle-employee-block/<int:id>/',   toggle_employee_block, name='toggle_employee_block'),
    
    # AJAX Validation
    path('check-email-unique/',   check_email_unique, name='check_email_unique'),
    path('check-username-unique/',   check_username_unique, name='check_username_unique'),
    path('check-employee-id-unique/', check_employee_id_unique, name='check_employee_id_unique'),


    # ==================== TASK ASSIGNMENT URLs ====================
    
    # Super Admin URLs
    path('tasks/assign/', assign_task, name='assign_task'),
    path('tasks/admin/list/', admin_task_list, name='admin_task_list'),
    path('tasks/admin/detail/<int:task_id>/', admin_view_task_detail, name='admin_view_task_detail'),
    path('tasks/delete/<int:task_id>/', delete_task, name='delete_task'),
    
    # AJAX URLs
    path('tasks/ajax/get-employees-by-role/', get_employees_by_role_ajax, name='get_employees_by_role_ajax'),
    path('tasks/ajax/timer/<int:task_id>/', get_task_timer, name='get_task_timer'),
    
    # Employee URLs
    path('tasks/my-tasks/', my_assigned_tasks, name='my_assigned_tasks'),
    path('tasks/detail/<int:task_id>/', view_task_detail, name='view_task_detail'),
    path('tasks/accept/<int:task_id>/', accept_task, name='accept_task'),
    path('tasks/complete/<int:task_id>/', complete_task, name='complete_task'),


    # ------------------------------- Sales -----------------------------------


    path('clients/', client_list, name='client_list'),
    path('clients/add/', add_client, name='add_client'),
    path('clients/edit/<int:id>/', edit_client, name='edit_client'),
    path('clients/delete/<int:id>/', delete_client, name='delete_client'),
    path('clients/interested/', interested_clients, name='interested_clients'),
    path('clients/<int:client_id>/add-call/', add_call_log, name='add_call_log'),


    # ---------------------------- Project Assigned -------------------------

    path('projects/', project_list, name='project_list'),
    path('projects/create/<int:client_id>/', create_project, name='create_project'),
    path('projects/edit/<int:id>/', edit_project, name='edit_project'),
    path('projects/delete/<int:id>/', delete_project, name='delete_project'),
    path('projects/update-status/<int:id>/', update_project_status, name='update_project_status'),
    path('projects/<int:id>/', project_detail, name='project_detail'),
    path('projects/assign/', assign_project, name='assign_project'),
    path('projects/remove-assignment/<int:assignment_id>/', remove_project_assignment, name='remove_assignment'),

    # AJAX
    path('api/get-employees-by-role/', get_employees_by_role, name='get_employees_by_role'),



    # ------------------------------- WORK REPORTS ------------------------------
    path('work-reports/add/',add_work_report, name='add_work_report'),
    path('work-reports/my-reports/',my_work_reports, name='my_work_reports'),
    path('work-reports/all/',all_work_reports, name='all_work_reports'),
    path('work-reports/view/<int:id>/',view_work_report, name='view_work_report'),
    path('work-reports/edit/<int:id>/',edit_work_report, name='edit_work_report'),
    path('work-reports/delete/<int:id>/',delete_work_report, name='delete_work_report'),
    path('work-reports/review/<int:id>/',review_work_report, name='review_work_report'),

    # AJAX
    path('ajax/get-project-details/',get_project_details, name='get_project_details'),



    # ----------------------------- Holiday -------------------------------

    path('holidays/add/', add_holiday, name='add_holiday'),
    path('holidays/list/', holiday_list, name='holiday_list'),
    path('holidays/edit/<int:id>/', edit_holiday, name='edit_holiday'),
    path('holidays/delete/<int:id>/', delete_holiday, name='delete_holiday'),
    path('holidays/upcoming/', upcoming_holidays, name='upcoming_holidays'),


    # ------------------------ Leave & Attendnace -----------------------------
    # Leave URLs (existing)
    path('leave/apply/', apply_leave, name='apply_leave'),
    path('leave/my-applications/', my_leave_applications, name='my_leave_applications'),
    path('leave/pending/', pending_leave_requests, name='pending_leave_requests'),
    path('leave/approve/<int:id>/', approve_reject_leave, name='approve_reject_leave'),
    path('leave/detail/<int:id>/', view_leave_detail, name='view_leave_detail'),
    path('leave/all/', all_leave_applications, name='all_leave_applications'),
    path('leave/refund/<int:leave_id>/', refund_leave, name='refund_leave'),

    # NEW Attendance URLs
    path('attendance/punch/', punch_attendance, name='punch_attendance'),
    path('attendance/process-punch/', process_punch, name='process_punch'),
    path('attendance/my/', my_attendance, name='my_attendance'),
    path('attendance/list/', attendance_list, name='attendance_list'),

    path('attendance/list/', attendance_list, name='attendance_list'),
    path('attendance/detail/<int:attendance_id>/', get_attendance_detail, name='get_attendance_detail'),
    path('attendance/approve/', approve_monthly_attendance, name='approve_monthly_attendance'),

    # Attendance Status Change
    path('attendance/change-status/', change_attendance_status, name='change_attendance_status'),
    path('attendance/change-logs/<int:attendance_id>/', get_attendance_change_logs, name='get_attendance_change_logs'),
    

    # ==================== SALARY MANAGEMENT ====================
    
    # Main salary sheet page
    path('salary/sheet/', salary_sheet, name='salary_sheet'),
    
    # API endpoints
    path('api/get_salary_data/', get_salary_data, name='get_salary_data'),
    path('api/save_salary_data/', save_salary_data, name='save_salary_data'),
    
    # History views
    path('salary/history/', view_salary_history, name='view_salary_history'),
    path('my-salary-slips/', my_salary_slips, name='my_salary_slips'),
    
    # Individual salary slip view (PDF-ready)
    path('salary/slip/<int:salary_id>/', view_salary_slip, name='view_salary_slip'),

    

    # ============================== NEW URLS ===============================
    # Finance URLs
    path('finance/dashboard/', financial_dashboard, name='financial_dashboard'),
    path('finance/initialize/', initialize_company_funds, name='initialize_company_funds'),
    path('finance/transactions/', all_transactions, name='all_transactions'),

    # Project Payments
    path('project/<int:project_id>/record-payment/', record_client_payment, name='record_client_payment'),
    path('project/<int:id>/financial-detail/', project_financial_detail, name='project_financial_detail'),

    # Salary Payments
    path('salary/<int:salary_id>/pay-from-funds/', pay_salary_from_funds, name='pay_salary_from_funds'),

    # Expenses URLs
    path('expenses/add/', add_expense, name='add_expense'),
    path('expenses/list/', expense_list, name='expense_list'),
    path('expenses/delete/<int:expense_id>/', delete_expense, name='delete_expense'),

]