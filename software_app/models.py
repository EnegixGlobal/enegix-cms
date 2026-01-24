from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal  # Add this import at top
from datetime import date, timedelta, datetime, time





#  AdminUser model - Only for Super Admin now
class AdminUser(models.Model):
    ADMIN_ROLE_CHOICES = (
        ('super_admin', 'Super Admin'),
    )
    
    admin_id = models.CharField(max_length=10, unique=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ADMIN_ROLE_CHOICES, default='super_admin')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.admin_id} - {self.full_name} ({self.role})"


class CompanyFunds(models.Model):
    """
    Company ki total available funds
    Single row table - only ONE record exists
    """
    total_funds = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Breakdown
    total_received_from_clients = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid_as_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Last updated
    last_updated = models.DateTimeField(auto_now=True)
    updated_by_name = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        verbose_name = "Company Funds"
        verbose_name_plural = "Company Funds"
    
    def __str__(self):
        return f"Total Funds: ₹{self.total_funds}"


class FundTransaction(models.Model):
    """
    Every money IN/OUT transaction
    """
    TRANSACTION_TYPE_CHOICES = (
        ('initial_deposit', 'Initial Deposit'),          # Super admin adds funds
        ('client_payment', 'Client Payment'),            # Client pays for project
        ('salary_payment', 'Salary Payment'),            # Employee salary paid
        ('adjustment', 'Manual Adjustment'),             # Admin correction
    )
    
    transaction_id = models.CharField(max_length=20, unique=True, editable=False)
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Credit (+) or Debit (-)
    is_credit = models.BooleanField(help_text="True = Money IN, False = Money OUT")
    
    # Balance after this transaction
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Reference to related models
    project = models.ForeignKey(
        'Project', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='fund_transactions'
    )
    salary = models.ForeignKey(
        'MonthlySalary',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fund_transactions'
    )
    
    # Description
    description = models.TextField()
    
    # Who made this transaction
    created_by_admin = models.ForeignKey(
        'AdminUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_by_name = models.CharField(max_length=100)
    created_by_role = models.CharField(max_length=50)
    
    # Timestamps
    transaction_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-transaction_date']
    
    def save(self, *args, **kwargs):
        # Auto-generate transaction_id: TXN20250101001
        if not self.transaction_id:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_txn = FundTransaction.objects.filter(
                transaction_id__startswith=f'TXN{date_str}'
            ).order_by('-id').first()
            
            if last_txn:
                last_num = int(last_txn.transaction_id[-3:])
                self.transaction_id = f'TXN{date_str}{str(last_num + 1).zfill(3)}'
            else:
                self.transaction_id = f'TXN{date_str}001'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        sign = '+' if self.is_credit else '-'
        return f"{self.transaction_id} - {sign}₹{self.amount}"


class CompanyExpense(models.Model):
    """
    Simple company expenses tracking (pantry, utilities, etc.)
    """
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('company_card', 'Company Card'),
    )
    
    expense_id = models.CharField(max_length=20, unique=True, editable=False)
    
    expense_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(help_text="Kisliye kharcha hua? (Pantry, Electricity, etc.)")
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='cash')
    
    # Link to fund transaction (auto deduct from funds)
    fund_transaction = models.ForeignKey(
        'FundTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Who added this
    added_by_name = models.CharField(max_length=100)
    added_by_role = models.CharField(max_length=50)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-expense_date', '-created_at']
    
    def save(self, *args, **kwargs):
        # Auto-generate expense_id: EXP20250101001
        if not self.expense_id:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_exp = CompanyExpense.objects.filter(
                expense_id__startswith=f'EXP{date_str}'
            ).order_by('-id').first()
            
            if last_exp:
                last_num = int(last_exp.expense_id[-3:])
                self.expense_id = f'EXP{date_str}{str(last_num + 1).zfill(3)}'
            else:
                self.expense_id = f'EXP{date_str}001'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.expense_id} - ₹{self.amount} - {self.description[:30]}"


# =========================== EMPLOYEE ========================

class Employee(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )
    
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('hr', 'HR'),
        ('sales', 'Sales'),
        ('developer', 'Developer'),
        ('seos', 'Seos'),
        ('digital_marketing', 'Digital Marketing'), 
    )
    
    # Step 1 - Basic Info
    employee_id = models.CharField(max_length=10, unique=True, editable=False)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=10, default="9191919191")
    dob = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    profile_pic = models.ImageField(upload_to='employee_profiles/', blank=True, null=True)
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=255)
    
    # Step 2 - Address Details
    address_line = models.TextField()
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    pincode = models.CharField(max_length=10)
    
    # Step 3 - Emergency Contact
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_number = models.CharField(max_length=15)
    emergency_contact_relation = models.CharField(max_length=50)
    
    # Step 4 - Role & Professional Details
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    designation = models.CharField(max_length=100)
    base_salary = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Monthly base salary"
    )
    resume = models.FileField(upload_to='employee_resumes/', blank=True, null=True)
    
    # Step 5 - Bank Details
    account_number = models.CharField(max_length=20, blank=True, null=True)
    ifsc_code = models.CharField(max_length=11, blank=True, null=True)
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_address = models.TextField(blank=True, null=True)
    
    # 🔥 Training tracking
    is_in_training = models.BooleanField(
        default=False,
        help_text="First 7 ACTUAL training days (excluding holidays/absents)"
    )
    training_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when employee joined"
    )
    training_per_day_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100.00,
        help_text="Daily salary during training (₹100)"
    )
    
    # Additional Fields
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    blocked_by = models.ForeignKey(
        'AdminUser',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="blocked_employees"
    )
    blocked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.employee_id:
            last_employee = Employee.objects.all().order_by('id').last()
            if last_employee:
                last_id = int(last_employee.employee_id[3:])
                self.employee_id = f'EMP{str(last_id + 1).zfill(3)}'
            else:
                self.employee_id = 'EMP001'
        
        super(Employee, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"
    
    # 🔥 UPDATED: Check based on ACTUAL training days, not calendar days
    def check_training_status(self):
        """
        Auto-update training status based on:
        ✅ 7 ACTUAL TRAINING DAYS COMPLETED (status='training')
        
        Sunday, Holiday, Absent, LWP = NOT COUNTED
        Only 'training' status attendance counts
        """
        if not self.is_in_training:
            return False
        
        if not self.training_start_date:
            return True
        
        # 🔥 Count only 'training' status attendance
        training_days_completed = Attendance.objects.filter(
            employee=self,
            status='training',
            attendance_date__gte=self.training_start_date
        ).count()
        
        # 🔥 If 7 training days completed → Mark training complete
        if training_days_completed >= 7:
            self.is_in_training = False
            self.save()
            return False
        
        return True
    
    @property
    def training_days_remaining(self):
        """
        Returns how many more ACTUAL training days are needed
        """
        if not self.is_in_training:
            return 0
        
        if not self.training_start_date:
            return 7
        
        completed = Attendance.objects.filter(
            employee=self,
            status='training',
            attendance_date__gte=self.training_start_date
        ).count()
        
        return max(0, 7 - completed)


class EmployeeDocument(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
    document_name = models.CharField(max_length=100)
    document_file = models.FileField(upload_to='employee_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.document_name}"



# ==================== TASK ASSIGNMENT MODULE ====================

class TaskAssignment(models.Model):
    PRIORITY_CHOICES = (
        ('urgent', 'Urgent'),
        ('high', 'High'),
        ('normal', 'Normal'),
        ('low', 'Low'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),           # Just assigned, not seen by employee
        ('accepted', 'Accepted'),         # Employee accepted, timer started
        ('in_progress', 'In Progress'),   # Same as accepted (optional)
        ('completed', 'Completed'),       # Employee completed
        ('verified', 'Verified'),         # Super admin verified (optional for future)
    )
    
    task_id = models.CharField(max_length=15, unique=True, editable=False)
    
    # Assignment Info
    assigned_to = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='assigned_tasks'
    )
    assigned_to_id_display = models.CharField(max_length=10)
    assigned_to_name = models.CharField(max_length=100)
    assigned_to_role = models.CharField(max_length=50)
    
    # Task Details
    task_title = models.CharField(max_length=200, help_text="Short task title")
    task_description = models.TextField(help_text="Detailed task description")
    task_file = models.FileField(upload_to='task_files/', blank=True, null=True, help_text="Reference file")
    
    # Deadline & Priority
    due_date = models.DateField(help_text="Task deadline date")
    due_time = models.TimeField(help_text="Task deadline time")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Status & Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    assigned_date = models.DateTimeField(auto_now_add=True)
    accepted_date = models.DateTimeField(blank=True, null=True, help_text="When employee accepted")
    completed_date = models.DateTimeField(blank=True, null=True, help_text="When employee completed")
    
    # Completion Details
    completion_notes = models.TextField(blank=True, null=True, help_text="Employee's completion report")
    
    # Time Tracking (in minutes)
    time_taken_minutes = models.IntegerField(default=0, help_text="Time from accept to complete")
    
    # Assigned By (Super Admin)
    assigned_by_admin = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks_assigned'
    )
    assigned_by_name = models.CharField(max_length=100)
    assigned_by_role = models.CharField(max_length=50, default='super_admin')
    
    # Admin Review (Optional for future)
    admin_remarks = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-assigned_date']
        verbose_name = "Task Assignment"
        verbose_name_plural = "Task Assignments"
    
    def save(self, *args, **kwargs):
        # Auto-generate task_id
        if not self.task_id:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_task = TaskAssignment.objects.filter(
                task_id__startswith=f'TSK{date_str}'
            ).order_by('-id').first()
            
            if last_task:
                last_num = int(last_task.task_id[-3:])
                self.task_id = f'TSK{date_str}{str(last_num + 1).zfill(3)}'
            else:
                self.task_id = f'TSK{date_str}001'
        
        # Auto-calculate time taken (if completed)
        if self.status == 'completed' and self.accepted_date and self.completed_date:
            time_diff = self.completed_date - self.accepted_date
            self.time_taken_minutes = int(time_diff.total_seconds() / 60)
        
        super(TaskAssignment, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.task_id} - {self.assigned_to_name} - {self.task_title}"
    
    # In models.py - Replace the is_overdue property in TaskAssignment model

    @property
    def is_overdue(self):
        """Check if task is overdue"""
        if self.status in ['completed', 'verified']:
            return False
        
        from datetime import datetime
        
        # Create deadline datetime (naive)
        deadline = datetime.combine(self.due_date, self.due_time)
        
        # Get current time (naive)
        now = datetime.now()
        
        return now > deadline


    @property
    def time_remaining(self):
        """Get time remaining until deadline"""
        from datetime import datetime
        
        # Create deadline datetime (naive)
        deadline = datetime.combine(self.due_date, self.due_time)
        
        # Get current time (naive)
        now = datetime.now()
        
        if now > deadline:
            return "Overdue"
        
        diff = deadline - now
        hours = int(diff.total_seconds() / 3600)
        minutes = int((diff.total_seconds() % 3600) / 60)
        
        if hours > 24:
            days = hours // 24
            return f"{days} days"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"    



class TaskCompletionFile(models.Model):
    """
    Multiple files can be uploaded when completing a task
    """
    task = models.ForeignKey(
        TaskAssignment,
        on_delete=models.CASCADE,
        related_name='completion_files'
    )
    file = models.FileField(upload_to='task_completion_files/')
    file_name = models.CharField(max_length=200)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"{self.task.task_id} - {self.file_name}"





# =========================== Sales ============================

class Client(models.Model):
    STATUS_CHOICES = (
        ('contacted', 'Contacted'),
        ('follow_up', 'Follow Up'),
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
    )
    
    client_id = models.CharField(max_length=10, unique=True, editable=False)
    company_name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100)
    email = models.EmailField()
    mobile = models.CharField(max_length=15)
    address = models.TextField(blank=True, null=True)
    
    # Sales tracking - UPDATED: Now nullable and tracks by name
    added_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='clients_added')
    added_by_name = models.CharField(max_length=100, blank=True, null=True)  # NEW: Store name
    added_by_role = models.CharField(max_length=50, blank=True, null=True)   # NEW: Store role
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='contacted')
    
    # Call tracking
    total_calls = models.IntegerField(default=0)
    last_call_date = models.DateField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_active = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        if not self.client_id:
            last_client = Client.objects.all().order_by('id').last()
            if last_client:
                last_id = int(last_client.client_id[3:])
                self.client_id = f'CLT{str(last_id + 1).zfill(3)}'
            else:
                self.client_id = 'CLT001'
        super(Client, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.client_id} - {self.company_name}"


class ClientCallLog(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='call_logs')
    
    # UPDATED: Flexible called_by - stores both Employee FK and text info
    called_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    called_by_name = models.CharField(max_length=100, default = "")  # NEW: Always store name
    called_by_role = models.CharField(max_length=50, default = "")   # NEW: Always store role
    
    call_date = models.DateField()
    call_time = models.TimeField()
    duration = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField()
    next_follow_up = models.DateField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-call_date', '-call_time']
    
    def __str__(self):
        return f"{self.client.company_name} - {self.call_date} by {self.called_by_name}"





# =========================== Projects ============================

class Project(models.Model):
    PROJECT_TYPE_CHOICES = (
        ('seo', 'SEO Project'),
        ('development', 'Development Project'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    )
    
    project_id = models.CharField(max_length=10, unique=True, editable=False)
    project_name = models.CharField(max_length=200)
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPE_CHOICES)
    
    # Linked to interested client
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects')
    
    # Project details
    description = models.TextField()
    start_date = models.DateField()
    deadline = models.DateField()
    budget = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        help_text="Total project value in INR"
    )
    
    amount_received = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Total amount received from client"
    )
    
    amount_pending = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Remaining amount to be received"
    )
    
    payment_status = models.CharField(
        max_length=20,
        choices=(
            ('unpaid', 'Unpaid'),
            ('partial', 'Partially Paid'),
            ('paid', 'Fully Paid'),
        ),
        default='unpaid'
    )
    
    # NEW: File uploads
    agreement = models.FileField(upload_to='project_agreements/', blank=True, null=True)
    module_file = models.FileField(upload_to='project_modules/', blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Who created this project
    created_by_name = models.CharField(max_length=100)
    created_by_role = models.CharField(max_length=50)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_active = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        if not self.project_id:
            last_project = Project.objects.all().order_by('id').last()
            if last_project:
                last_id = int(last_project.project_id[3:])
                self.project_id = f'PRJ{str(last_id + 1).zfill(3)}'
            else:
                self.project_id = 'PRJ001'
        super(Project, self).save(*args, **kwargs)

    def update_payment_status(self):
        """Auto-calculate payment status"""
        from django.db.models import Sum
        
        self.amount_received = self.payments.aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0')
        
        self.amount_pending = self.total_amount - self.amount_received
        
        if self.amount_received == 0:
            self.payment_status = 'unpaid'
        elif self.amount_received >= self.total_amount:
            self.payment_status = 'paid'
            self.amount_pending = Decimal('0')  # Cap at 0
        else:
            self.payment_status = 'partial'
        
        self.save()
    
    def __str__(self):
        return f"{self.project_id} - {self.project_name}"


class ProjectAssignment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='project_assignments')
    
    # Auto-filled from employee
    employees_id = models.CharField(max_length=10)
    employee_name = models.CharField(max_length=100)
    employee_role = models.CharField(max_length=50)
    employee_designation = models.CharField(max_length=100)
    
    # Assignment details
    assigned_date = models.DateField(auto_now_add=True)
    assigned_by_name = models.CharField(max_length=100)
    assigned_by_role = models.CharField(max_length=50)
    
    notes = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('project', 'employee')
    
    def __str__(self):
        return f"{self.project.project_name} - {self.employee_name}"


class ProjectPayment(models.Model):
    """
    Track payments for each project
    Multiple payments can be made for one project
    """
    payment_id = models.CharField(max_length=20, unique=True, editable=False)
    
    project = models.ForeignKey(
        'Project',
        on_delete=models.CASCADE,
        related_name='payments'
    )
    
    # Payment details
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(
        max_length=30,
        choices=(
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('cheque', 'Cheque'),
            ('upi', 'UPI'),
            ('other', 'Other'),
        ),
        default='bank_transfer'
    )
    
    # Reference (cheque no, transaction id, etc)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    
    # Receipt/proof
    payment_proof = models.FileField(upload_to='payment_proofs/', blank=True, null=True)
    
    # Notes
    remarks = models.TextField(blank=True, null=True)
    
    # Who recorded this payment
    recorded_by_name = models.CharField(max_length=100)
    recorded_by_role = models.CharField(max_length=50)
    
    # Link to fund transaction
    fund_transaction = models.ForeignKey(
        'FundTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def save(self, *args, **kwargs):
        # Auto-generate payment_id: PAY20250101001
        if not self.payment_id:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_pay = ProjectPayment.objects.filter(
                payment_id__startswith=f'PAY{date_str}'
            ).order_by('-id').first()
            
            if last_pay:
                last_num = int(last_pay.payment_id[-3:])
                self.payment_id = f'PAY{date_str}{str(last_num + 1).zfill(3)}'
            else:
                self.payment_id = f'PAY{date_str}001'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.payment_id} - {self.project.project_name} - ₹{self.amount_paid}"



class DailyWorkReport(models.Model):
    TASK_STATUS_CHOICES = (
        ('completed', 'Completed'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
        ('blocked', 'Blocked'),
    )
    
    report_id = models.CharField(max_length=15, unique=True, editable=False)
    
    # Project & Employee Info (Auto-filled)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='work_reports')
    project_id_display = models.CharField(max_length=10)  # Auto from project
    project_name = models.CharField(max_length=200)  # Auto from project
    project_type = models.CharField(max_length=20)  # Auto from project
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='work_reports')
    employee_id_display = models.CharField(max_length=10)  # Auto from employee
    employee_name = models.CharField(max_length=100)  # Auto from employee
    employee_role = models.CharField(max_length=50)  # Auto from employee
    
    # Work Details
    work_date = models.DateField()
    hours_worked = models.DecimalField(max_digits=4, decimal_places=2, help_text="Hours spent on this project")
    
    # Task Summary
    tasks_completed = models.TextField(help_text="What tasks did you complete today?")
    tasks_in_progress = models.TextField(blank=True, null=True, help_text="What are you currently working on?")
    tasks_planned = models.TextField(blank=True, null=True, help_text="What do you plan to work on next?")
    
    # Challenges & Support
    challenges_faced = models.TextField(blank=True, null=True, help_text="Any blockers or challenges?")
    support_needed = models.TextField(blank=True, null=True, help_text="Do you need any help or resources?")
    
    # Status
    overall_status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES, default='in_progress')
    
    # Additional Notes
    additional_notes = models.TextField(blank=True, null=True, help_text="Any other important information")
    
    # File attachments (screenshots, documents, etc.)
    attachment_1 = models.FileField(upload_to='work_reports/', blank=True, null=True)
    attachment_2 = models.FileField(upload_to='work_reports/', blank=True, null=True)
    attachment_3 = models.FileField(upload_to='work_reports/', blank=True, null=True)
    
    # Admin Review
    is_reviewed = models.BooleanField(default=False)
    reviewed_by_name = models.CharField(max_length=100, blank=True, null=True)
    reviewed_by_role = models.CharField(max_length=50, blank=True, null=True)
    review_date = models.DateTimeField(blank=True, null=True)
    admin_feedback = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-work_date', '-created_at']
        unique_together = ('project', 'employee', 'work_date')  # One report per project per day
    
    def save(self, *args, **kwargs):
        if not self.report_id:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_report = DailyWorkReport.objects.filter(
                report_id__startswith=f'RPT{date_str}'
            ).order_by('-id').first()
            
            if last_report:
                last_num = int(last_report.report_id[-3:])
                self.report_id = f'RPT{date_str}{str(last_num + 1).zfill(3)}'
            else:
                self.report_id = f'RPT{date_str}001'
        
        super(DailyWorkReport, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.report_id} - {self.employee_name} - {self.work_date}"




# ======================= Holiday ====================


class HolidayMaster(models.Model):
    """Public holidays managed by Super Admin"""
    holiday_id = models.CharField(max_length=10, unique=True, editable=False)
    holiday_name = models.CharField(max_length=200, help_text="e.g., Diwali, Independence Day")
    holiday_date = models.DateField(unique=True)
    holiday_type = models.CharField(
        max_length=20,
        choices=(
            ('festival', 'Festival'),
            ('national', 'National Holiday'),
            ('other', 'Other'),
        ),
        default='festival'
    )
    description = models.TextField(blank=True, null=True)
    
    # Who created/managed this holiday
    created_by_name = models.CharField(max_length=100)
    created_by_role = models.CharField(max_length=50)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['holiday_date']
    
    def save(self, *args, **kwargs):
        if not self.holiday_id:
            last_holiday = HolidayMaster.objects.all().order_by('id').last()
            if last_holiday:
                last_id = int(last_holiday.holiday_id[3:])
                self.holiday_id = f'HOL{str(last_id + 1).zfill(3)}'
            else:
                self.holiday_id = 'HOL001'
        super(HolidayMaster, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.holiday_id} - {self.holiday_name} ({self.holiday_date})"



# ================== Leave ==============================

class EmployeeLeaveBalance(models.Model):
    """
    ✅ CORRECT LOGIC:
    - 1 Casual Leave per month (12 total yearly)
    - 6 Sick Leaves per year (use anytime)
    - Track monthly casual usage
    """
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='leave_balance')
    
    # Yearly sick leave bucket (6 total)
    sick_leave_balance = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=6.0,
        help_text="Total sick leaves for the year (6 max)"
    )
    
    # Monthly casual leave tracking
    casual_leaves_taken_this_month = models.IntegerField(
        default=0,
        help_text="Casual leaves used in current month"
    )
    
    # Track current month/year for reset
    current_month = models.IntegerField(default=timezone.now().month)
    current_year = models.IntegerField(default=timezone.now().year)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def casual_leaves_available_this_month(self):
        """How many casual leaves available THIS MONTH"""
        now = timezone.now()
        
        # Reset if new month
        if self.current_month != now.month or self.current_year != now.year:
            self.casual_leaves_taken_this_month = 0
            self.current_month = now.month
            self.current_year = now.year
            self.save()
        
        # Only 1 casual per month
        return max(0, 1 - self.casual_leaves_taken_this_month)
    
    @property
    def total_casual_leaves_used_yearly(self):
        """Total casual leaves used this year"""
        return LeaveApplication.objects.filter(
            employee=self.employee,
            status='approved',
            from_date__year=self.current_year,
            casual_days_deducted__gt=0
        ).aggregate(total=Sum('casual_days_deducted'))['total'] or 0
    
    def __str__(self):
        return f"{self.employee.full_name} - Casual (Month): {self.casual_leaves_available_this_month}/1, Sick (Year): {self.sick_leave_balance}/6"
    
    class Meta:
        verbose_name = "Employee Leave Balance"
        verbose_name_plural = "Employee Leave Balances"


class LeaveApplication(models.Model):
    """
    ✅ NO 0.5 DAYS - Only integers allowed
    """
    LEAVE_TYPE_CHOICES = (
        ('casual', 'Casual Leave'),
        ('sick', 'Sick Leave'),
        ('combined', 'Combined Leave'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    leave_id = models.CharField(max_length=15, unique=True, editable=False)
    
    # Employee
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_applications')
    employee_id_display = models.CharField(max_length=10)
    employee_name = models.CharField(max_length=100)
    employee_role = models.CharField(max_length=50)
    
    # Leave details - CHANGED to IntegerField (NO 0.5)
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    from_date = models.DateField()
    to_date = models.DateField()
    total_days = models.IntegerField(help_text="Total working days requested")
    
    # Breakdown
    casual_days_requested = models.IntegerField(default=0)
    sick_days_requested = models.IntegerField(default=0)
    
    # Actual deductions (after approval)
    casual_days_deducted = models.IntegerField(default=0)
    sick_days_deducted = models.IntegerField(default=0)
    unpaid_days = models.IntegerField(default=0)
    
    # Other fields same as before
    reason = models.TextField()
    attachment = models.FileField(upload_to='leave_attachments/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    approved_by_name = models.CharField(max_length=100, blank=True, null=True)
    approved_by_role = models.CharField(max_length=50, blank=True, null=True)
    approval_date = models.DateTimeField(blank=True, null=True)
    hr_remarks = models.TextField(blank=True, null=True)
    
    applied_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Refund tracking
    days_actually_taken = models.IntegerField(default=0)
    refund_processed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-applied_date']
    
    def save(self, *args, **kwargs):
        if not self.leave_id:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_leave = LeaveApplication.objects.filter(
                leave_id__startswith=f'LV{date_str}'
            ).order_by('-id').first()
            
            if last_leave:
                last_num = int(last_leave.leave_id[-3:])
                self.leave_id = f'LV{date_str}{str(last_num + 1).zfill(3)}'
            else:
                self.leave_id = f'LV{date_str}001'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.leave_id} - {self.employee_name} ({self.status})"



# ================= Attendance ===================

class AttendancePunch(models.Model):
    """
    🆕 NEW MODEL: Geofencing-based attendance with breaks
    """
    PUNCH_TYPE_CHOICES = (
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('break_start', 'Break Start'),
        ('break_end', 'Break End'),
    )
    
    punch_id = models.CharField(max_length=20, unique=True, editable=False)
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='punches')
    employee_id_display = models.CharField(max_length=10)
    employee_name = models.CharField(max_length=100)
    
    # Punch details
    punch_type = models.CharField(max_length=15, choices=PUNCH_TYPE_CHOICES)
    punch_datetime = models.DateTimeField(auto_now_add=True)
    punch_date = models.DateField(auto_now_add=True)
    punch_time = models.TimeField(auto_now_add=True)
    
    # 🔥 Geofencing data
    latitude = models.DecimalField(max_digits=10, decimal_places=7, help_text="Punch location latitude")
    longitude = models.DecimalField(max_digits=10, decimal_places=7, help_text="Punch location longitude")
    is_within_geofence = models.BooleanField(default=False, help_text="Is punch within 30m radius?")
    distance_from_office = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        help_text="Distance in meters",
        null=True,
        blank=True
    )
    
    # Device info (optional for security)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['-punch_datetime']
    
    def save(self, *args, **kwargs):
        if not self.punch_id:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_punch = AttendancePunch.objects.filter(
                punch_id__startswith=f'PUN{date_str}'
            ).order_by('-id').first()
            
            if last_punch:
                last_num = int(last_punch.punch_id[-4:])
                self.punch_id = f'PUN{date_str}{str(last_num + 1).zfill(4)}'
            else:
                self.punch_id = f'PUN{date_str}0001'
        
        super(AttendancePunch, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.punch_id} - {self.employee_name} - {self.punch_type}"


class BreakLog(models.Model):
    """
    🆕 NEW MODEL: Track employee breaks
    """
    break_id = models.CharField(max_length=20, unique=True, editable=False)
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='breaks')
    attendance_date = models.DateField()
    
    # Break timing
    break_start = models.ForeignKey(
        AttendancePunch, 
        on_delete=models.CASCADE, 
        related_name='break_starts'
    )
    break_end = models.ForeignKey(
        AttendancePunch, 
        on_delete=models.CASCADE, 
        related_name='break_ends',
        null=True,
        blank=True
    )
    
    # Duration in minutes
    duration_minutes = models.IntegerField(default=0, help_text="Break duration in minutes")
    
    # Break type
    is_lunch_break = models.BooleanField(default=False, help_text="Is this the lunch break (2-3 PM)?")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.break_id:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_break = BreakLog.objects.filter(
                break_id__startswith=f'BRK{date_str}'
            ).order_by('-id').first()
            
            if last_break:
                last_num = int(last_break.break_id[-4:])
                self.break_id = f'BRK{date_str}{str(last_num + 1).zfill(4)}'
            else:
                self.break_id = f'BRK{date_str}0001'
        
        # Calculate duration if both start and end exist
        if self.break_start and self.break_end:
            start_dt = self.break_start.punch_datetime
            end_dt = self.break_end.punch_datetime
            self.duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
        
        super(BreakLog, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.break_id} - {self.employee.full_name} - {self.duration_minutes}m"


class Attendance(models.Model):
    """
    🔥 UPDATED: Added LWP and Training statuses
    """
    ATTENDANCE_STATUS_CHOICES = (
        ('present', 'Present (P)'),
        ('absent', 'Absent (A)'),
        ('half_day', 'Half Day (HD)'),
        ('on_leave', 'On Leave (L)'),
        ('holiday', 'Holiday (H)'),
        ('lwp', 'Leave Without Pay (LWP)'),  # ✅ Already exists
        ('ncnp', 'No Call No Present (NCNP)'),
        ('training', 'Training (T)'),  # 🔥 NEW
    )
    
    attendance_id = models.CharField(max_length=20, unique=True, editable=False)
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    employee_id_display = models.CharField(max_length=10)
    employee_name = models.CharField(max_length=100)
    
    attendance_date = models.DateField()
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES)
    
    # Punch references
    check_in_punch = models.ForeignKey(
        'AttendancePunch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkin_attendance'
    )
    check_out_punch = models.ForeignKey(
        'AttendancePunch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkout_attendance'
    )
    
    # Calculated fields
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    total_work_hours = models.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        default=0,
        help_text="Total working hours (excluding breaks)"
    )
    total_break_minutes = models.IntegerField(default=0, help_text="Total break time in minutes")
    
    # Late check-in flag
    is_late = models.BooleanField(default=False, help_text="Checked in after 10:30 AM")
    
    # Leave/Holiday references
    leave_application = models.ForeignKey(
        'LeaveApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_records'
    )
    holiday = models.ForeignKey(
        'HolidayMaster',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_records'
    )
    
    remarks = models.TextField(blank=True, null=True)
    
    # System fields
    auto_calculated = models.BooleanField(default=True, help_text="Auto-calculated from punches")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('employee', 'attendance_date')
        ordering = ['-attendance_date']
    
    def save(self, *args, **kwargs):
        if not self.attendance_id:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_att = Attendance.objects.filter(
                attendance_id__startswith=f'ATT{date_str}'
            ).order_by('-id').first()
            
            if last_att:
                last_num = int(last_att.attendance_id[-4:])
                self.attendance_id = f'ATT{date_str}{str(last_num + 1).zfill(4)}'
            else:
                self.attendance_id = f'ATT{date_str}0001'
        
        super(Attendance, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.attendance_id} - {self.employee_name} - {self.attendance_date} ({self.status})"




# ==================== UPDATED AttendanceStatusChangeLog ====================

class AttendanceStatusChangeLog(models.Model):
    """
    🔥 UPDATED: Added Training and LWP statuses
    """
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('half_day', 'Half Day'),
        ('absent', 'Absent'),
        ('on_leave', 'On Leave'),
        ('holiday', 'Holiday'),
        ('lwp', 'Leave Without Pay'),  # 🔥 NEW
        ('training', 'Training'),  # 🔥 NEW
    ]
    
    attendance = models.ForeignKey(
        'Attendance',
        on_delete=models.CASCADE,
        related_name='status_changes'
    )
    employee = models.ForeignKey(
        'Employee',
        on_delete=models.CASCADE,
        related_name='attendance_status_changes'
    )
    attendance_date = models.DateField()
    
    old_status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    new_status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    reason = models.TextField()
    
    # Track who made the change
    changed_by_employee = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_changes_made'
    )
    changed_by_admin = models.ForeignKey(
        'AdminUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_changes_made'
    )
    changed_by_name = models.CharField(max_length=200)
    changed_by_role = models.CharField(max_length=50)
    
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'attendance_status_change_logs'
        ordering = ['-changed_at']
        verbose_name = 'Attendance Status Change Log'
        verbose_name_plural = 'Attendance Status Change Logs'
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.attendance_date} - {self.old_status} to {self.new_status}"




# ==================== GEOFENCE CONFIG (Optional) ====================

class GeofenceConfig(models.Model):
    """
    Office geofence configuration
    """
    office_name = models.CharField(max_length=200, default="Head Office")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, default=23.351633)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, default=85.3162779)
    radius_meters = models.IntegerField(default=80, help_text="Geofence radius in meters")
    
    # Timing configurations
    office_start_time = models.TimeField(default='09:30:00')
    office_end_time = models.TimeField(default='18:30:00')
    lunch_break_start = models.TimeField(default='14:00:00')
    lunch_break_end = models.TimeField(default='15:00:00')
    late_threshold = models.TimeField(default='10:30:00', help_text="Late if check-in after this time")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Geofence Configuration"
        verbose_name_plural = "Geofence Configurations"
    
    def __str__(self):
        return f"{self.office_name} - {self.radius_meters}m radius"


class MonthlyAttendanceApproval(models.Model):
    """
    Track monthly attendance approval by HR/Admin
    Once approved, salary generation is triggered
    """
    approval_id = models.CharField(max_length=20, unique=True, editable=False)
    
    month = models.IntegerField(help_text="Month number (1-12)")
    year = models.IntegerField(help_text="Year")
    
    approved_by = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='attendance_approvals'
    )
    approved_by_admin = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_approvals'
    )
    approved_by_name = models.CharField(max_length=100)
    approved_by_role = models.CharField(max_length=50)
    
    approval_date = models.DateTimeField(auto_now_add=True)
    
    approved_up_to_date = models.DateField(null=True, blank=True, help_text="Date up to which attendance was approved")

    total_employees = models.IntegerField(help_text="Total active employees in this month")
    total_present_days = models.IntegerField(default=0)
    total_absent_days = models.IntegerField(default=0)
    total_half_days = models.IntegerField(default=0)
    total_leaves = models.IntegerField(default=0)
    
    status = models.CharField(
        max_length=20,
        choices=(
            ('approved', 'Approved'),
            ('locked', 'Locked'),
        ),
        default='approved'
    )
    
    # Salary generation flag
    salary_generated = models.BooleanField(default=False)
    salary_generation_date = models.DateTimeField(null=True, blank=True)
    
    remarks = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ('month', 'year')
        ordering = ['-year', '-month']
    
    def save(self, *args, **kwargs):
        if not self.approval_id:
            year_month = f"{self.year}{str(self.month).zfill(2)}"
            last_approval = MonthlyAttendanceApproval.objects.filter(
                approval_id__startswith=f'MAPPR{year_month}'
            ).order_by('-id').first()
            
            if last_approval:
                last_num = int(last_approval.approval_id[-3:])
                self.approval_id = f'MAPPR{year_month}{str(last_num + 1).zfill(3)}'
            else:
                self.approval_id = f'MAPPR{year_month}001'
        
        super(MonthlyAttendanceApproval, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.approval_id} - {self.month}/{self.year} by {self.approved_by_name}"



# ==================== CORRECTED SALARY MODEL ====================
# Now using PRESENT-BASED calculation (consistent across all views)

class MonthlySalary(models.Model):
    """
    Simple monthly salary record for each employee
    CALCULATION LOGIC: Base Salary ÷ 30 = Per Day Salary
    Then: (Present Days × Per Day) + (Leave Days × Per Day) + (Half Days × Per Day ÷ 2)
    """
    salary_id = models.CharField(max_length=20, unique=True, editable=False)
    
    # Employee Info
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='monthly_salaries')
    employee_id_display = models.CharField(max_length=10)
    employee_name = models.CharField(max_length=100)
    
    # Month/Year
    month = models.IntegerField(help_text="Month (1-12)")
    year = models.IntegerField(help_text="Year")

    # New fields
    fund_transaction = models.ForeignKey(
        'FundTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='salary_payments'
    )
    
    payment_from_funds = models.BooleanField(
        default=False,
        help_text="Was this salary paid from company funds?"
    )
    
    # Salary Components
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    per_day_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Attendance Summary (from Attendance model)
    total_present = models.IntegerField(default=0)
    total_absent = models.IntegerField(default=0)
    total_half_days = models.IntegerField(default=0)
    total_leaves = models.IntegerField(default=0)
    
    # Allowances (editable)
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    travel_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Statutory Deductions
    pf_percent = models.DecimalField(max_digits=5, decimal_places=2, default=12.00)
    pf_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    esi_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.75)
    esi_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Calculated Fields
    gross_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_payable = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Payment Tracking
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_date = models.DateField(null=True, blank=True)
    remaining_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Previous month balance
    previous_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    is_saved = models.BooleanField(default=False, help_text="Data saved permanently")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('employee', 'month', 'year')
        ordering = ['-year', '-month']
    
    def save(self, *args, **kwargs):
        # Auto-generate salary_id
        if not self.salary_id:
            year_month = f"{self.year}{str(self.month).zfill(2)}"
            last_salary = MonthlySalary.objects.filter(
                salary_id__startswith=f'SAL{year_month}'
            ).order_by('-id').first()
            
            if last_salary:
                last_num = int(last_salary.salary_id[-3:])
                self.salary_id = f'SAL{year_month}{str(last_num + 1).zfill(3)}'
            else:
                self.salary_id = f'SAL{year_month}001'
        
        # 🔥 UPDATED: Dynamic per day calculation based on month
        import calendar
        days_in_month = calendar.monthrange(self.year, self.month)[1]  # 28/29/30/31
        self.per_day_salary = self.base_salary / Decimal(str(days_in_month))
        
        # ✅ Calculate attendance salary properly
        present_salary = Decimal(str(self.total_present)) * self.per_day_salary
        leave_salary = Decimal(str(self.total_leaves)) * self.per_day_salary
        half_day_salary = Decimal(str(self.total_half_days)) * (self.per_day_salary / 2)
        
        # Attendance-based salary (Present + Leave + Half Day)
        attendance_salary = present_salary + leave_salary + half_day_salary
        
        # ✅ CAP: Attendance salary cannot exceed base_salary
        if attendance_salary > self.base_salary:
            attendance_salary = self.base_salary
        
        # Calculate gross (Capped Attendance Salary + Bonus + Travel Allowance)
        self.gross_salary = attendance_salary + self.bonus + self.travel_allowance
        
        # Calculate PF and ESI on gross salary
        self.pf_amount = (self.gross_salary * self.pf_percent) / Decimal('100')
        self.esi_amount = (self.gross_salary * self.esi_percent) / Decimal('100')
        
        # Total deductions (only statutory)
        self.total_deductions = self.pf_amount + self.esi_amount
        
        # Net payable
        self.net_payable = self.gross_salary - self.total_deductions + self.previous_balance
        
        # Remaining balance
        self.remaining_balance = self.net_payable - self.paid_amount
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.salary_id} - {self.employee_name} - {self.month}/{self.year}"


