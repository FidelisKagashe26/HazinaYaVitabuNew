from django.urls import path
from . import views
from .views import *
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    # Authentication URLs
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # Dashboard URLs
    path('buyer-dashboard/', views.buyer_dashboard, name='buyer_dashboard'),
    path('seller-dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('superuser-dashboard/', views.superuser_dashboard, name='superuser_dashboard'),
    
    # Order management URLs
    path('accept-order/<int:order_id>/', views.accept_order, name='accept_order'),
    path('accept-anonymous-order/<int:order_id>/', views.accept_anonymous_order, name='accept_anonymous_order'),
    path('complete-order/<int:order_id>/', views.complete_order, name='complete_order'),
    
    # Report URLs
    path('daily-report/', views.daily_report_view, name='daily_report'),
    path('view-reports/', views.view_reports, name='view_reports'),
    path('monthly-reports/', views.monthly_reports_view, name='monthly_reports'),
    path('generate-monthly-reports/', views.generate_monthly_reports, name='generate_monthly_reports'),
    
    # User management URLs
    path('manage-users/', views.manage_users, name='manage_users'),
    
    # Password Reset URLs
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset/new/', views.password_reset_new, name='password_reset_new'),
    
    # Language switching
    path('set-language/<str:language>/', views.set_language, name='set_language'),
    
    # Theme switching
    path('toggle-theme/', views.toggle_theme, name='toggle_theme'),

    path('about/', views.About, name='about'),
    path('shop/', views.Shop, name='shop'),
    path('faq/', views.Faq, name='faq'),
    path('contact/', views.Contact, name='contact'),
]