from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta

class UserProfile(models.Model):
    USER_ROLES = (
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
        ('superuser', 'Superuser'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # Remove unique=True if it exists
    phone_number = models.CharField(max_length=15)
    role = models.CharField(max_length=20, choices=USER_ROLES, default='buyer')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

from uuid import uuid4
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reset_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    uidb64 = models.CharField(max_length=64, blank=True, null=True)  # Store UID base64
    token = models.CharField(max_length=128, blank=True, null=True)  # Store token
    expires_at = models.DateTimeField(blank=True, null=True)  # Expiration time for the code and token
    request_token = models.UUIDField(default=uuid4, editable=False)  # Unique request token

    def __str__(self):
        return f"Reset Code for {self.user.email}"

    def is_expired(self):
        return timezone.now() > self.expires_at if self.expires_at else False

    def delete_if_expired_or_used(self, token_used=False):
        if self.is_expired() or token_used:
            self.delete()


class DailyReport(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_reports')
    date = models.DateField(default=timezone.now)
    books_sold_details = models.JSONField(default=list, help_text="List of books sold with quantities")
    books_given_free_details = models.JSONField(default=list, help_text="List of books given free with quantities")
    houses_visited = models.IntegerField(default=0, help_text="Number of houses visited")
    teachings_given = models.IntegerField(default=0, help_text="Number of teachings given")
    working_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0, help_text="Working hours in a day")
    additional_notes = models.TextField(blank=True, help_text="Additional notes or comments")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('seller', 'date')
        ordering = ['-date']
    
    def __str__(self):
        return f"Report for {self.seller.username} - {self.date}"
    
    @property
    def total_books_sold(self):
        """Calculate total books sold from details"""
        return sum(item.get('quantity', 0) for item in self.books_sold_details)
    
    @property
    def total_books_given_free(self):
        """Calculate total books given free from details"""
        return sum(item.get('quantity', 0) for item in self.books_given_free_details)


class MonthlyReport(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='monthly_reports')
    month = models.IntegerField()
    year = models.IntegerField()
    total_books_sold_money = models.IntegerField(default=0)
    total_books_given_free = models.IntegerField(default=0)
    total_houses_visited = models.IntegerField(default=0)
    total_teachings_given = models.IntegerField(default=0)
    total_working_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    average_daily_performance = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('seller', 'month', 'year')
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"Monthly Report for {self.seller.username} - {self.month}/{self.year}"
    
    @classmethod
    def generate_monthly_report(cls, seller, month, year):
        """Generate monthly report from daily reports"""
        daily_reports = DailyReport.objects.filter(
            seller=seller,
            date__month=month,
            date__year=year
        )
        
        if not daily_reports.exists():
            return None
            
        total_books_sold = sum(report.books_sold_money for report in daily_reports)
        total_books_free = sum(report.books_given_free for report in daily_reports)
        total_houses = sum(report.houses_visited for report in daily_reports)
        total_teachings = sum(report.teachings_given for report in daily_reports)
        total_hours = sum(report.working_hours for report in daily_reports)
        
        days_worked = daily_reports.count()
        
        monthly_report, created = cls.objects.get_or_create(
            seller=seller,
            month=month,
            year=year,
            defaults={
                'total_books_sold_money': total_books_sold,
                'total_books_given_free': total_books_free,
                'total_houses_visited': total_houses,
                'total_teachings_given': total_teachings,
                'total_working_hours': total_hours,
                'average_daily_performance': {
                    'avg_books_sold': round(total_books_sold / days_worked, 2) if days_worked > 0 else 0,
                    'avg_books_free': round(total_books_free / days_worked, 2) if days_worked > 0 else 0,
                    'avg_houses': round(total_houses / days_worked, 2) if days_worked > 0 else 0,
                    'avg_teachings': round(total_teachings / days_worked, 2) if days_worked > 0 else 0,
                    'avg_hours': round(float(total_hours) / days_worked, 2) if days_worked > 0 else 0,
                    'days_worked': days_worked
                }
            }
        )
        
        return monthly_report


class AnonymousOrder(models.Model):
    """Temporary model to store anonymous user orders before they register"""
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=15)
    delivery_address = models.TextField()
    order_data = models.JSONField()  # Store cart items data
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)
    assigned_seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_anonymous_orders')
    
    def __str__(self):
        return f"Anonymous Order - {self.customer_name} ({self.customer_email})"
