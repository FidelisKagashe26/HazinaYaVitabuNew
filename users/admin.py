from django.contrib import admin
from .models import UserProfile, PasswordResetCode, DailyReport, MonthlyReport

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    # Display user email and username through the related User model
    list_display = ('user_email', 'user_username', 'phone_number', 'role', 'is_active', 'created_at')

    # Search through User's email, username, and phone number
    search_fields = ('user__email', 'user__username', 'phone_number', 'role') 

    # Filter by username from the related User model
    list_filter = ('role', 'is_active', 'created_at')  

    # Prevent editing the email field from the related User model (readonly)
    readonly_fields = ('user_email', 'created_at')  

    def has_add_permission(self, request):
        """Prevent adding new UserProfile objects from the admin."""
        return False

    def user_email(self, obj):
        """Custom method to access the user's email from the related User model."""
        return obj.user.email

    user_email.short_description = 'Email'  # Label for the 'user_email' field in the admin

    def user_username(self, obj):
        """Custom method to access the user's username from the related User model."""
        return obj.user.username

    user_username.short_description = 'Username'  # Label for the 'user_username' field in the admin


@admin.register(PasswordResetCode)
class PasswordResetCodeAdmin(admin.ModelAdmin):
    # Display all fields of the PasswordResetCode model
    list_display = (
        'user_email', 
        'reset_code', 
        'created_at', 
        'uidb64', 
        'token', 
        'expires_at', 
        'request_token'
    )

    # Search through User's email and reset code
    search_fields = ('user__email', 'reset_code')

    # Filter by username from the related User model
    list_filter = ('user__username',)

    # Prevent editing the email field from the related User model (readonly)
    readonly_fields = ('user_email', 'reset_code', 'created_at', 'uidb64', 'token', 'expires_at', 'request_token')

    # Custom method to retrieve user's email
    def user_email(self, obj):
        """Custom method to access the user's email from the related User model."""
        return obj.user.email

    user_email.short_description = 'Email'  # Label for the 'user_email' field in the admin


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ('seller_name', 'date', 'total_books_sold', 'total_books_given_free', 'houses_visited', 'teachings_given', 'working_hours')
    list_filter = ('date', 'seller__username')
    search_fields = ('seller__username', 'seller__email')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'
    
    def seller_name(self, obj):
        return obj.seller.username
    seller_name.short_description = 'Seller'


@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ('seller_name', 'month', 'year', 'total_books_sold_money', 'total_books_given_free', 'total_working_hours')
    list_filter = ('year', 'month', 'seller__username')
    search_fields = ('seller__username', 'seller__email')
    readonly_fields = ('generated_at', 'average_daily_performance')
    
    def seller_name(self, obj):
        return obj.seller.username
    seller_name.short_description = 'Seller'