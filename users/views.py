from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.views import LoginView
from users.models import UserProfile, PasswordResetCode, DailyReport, MonthlyReport, AnonymousOrder
from users.forms import RegistrationForm, UserForm, UserProfileForm
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import activate, get_language
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils.translation import gettext as _
from django.contrib.auth import login
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from datetime import timedelta
from django.conf import settings
from products.models import Category, Product, Cart, CartItem, Order, OrderItem
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import CustomAuthenticationForm
from django.views.generic import FormView
import random
from datetime import date
import string
from django.utils.encoding import force_bytes, force_str
from datetime import datetime, timedelta
from django.db.models import Q
from functools import wraps


def role_required(allowed_roles):
    """Decorator to check if user has required role"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            try:
                user_profile = request.user.userprofile
                if user_profile.role not in allowed_roles:
                    messages.error(request, _('You do not have permission to access this page.'))
                    return redirect('home')
            except UserProfile.DoesNotExist:
                messages.error(request, _('User profile not found.'))
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def register_view(request):
    """User registration view"""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    cart_item_count = get_cart_item_count(request)
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create user profile
            UserProfile.objects.create(
                user=user,
                phone_number=form.cleaned_data.get('phone_number', ''),
                role='buyer'  # Default role for self-registered users
            )
            username = form.cleaned_data.get('username')
            messages.success(request, _('Account created successfully! You can now log in.'))
            return redirect('login')
    else:
        form = RegistrationForm()
    
    context = {
        'form': form,
        'categories': categories,
        'cart_item_count': cart_item_count,
        'current_tab': 'register',
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/register.html', context)

def login_view(request):
    """User login view"""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    cart_item_count = get_cart_item_count(request)
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # Role-based redirection
                try:
                    user_profile = user.userprofile
                    if user_profile.role == 'seller':
                        messages.success(request, _('Welcome back, %(username)s!') % {'username': username})
                        return redirect('seller_dashboard')
                    elif user_profile.role == 'superuser':
                        messages.success(request, _('Welcome back, %(username)s!') % {'username': username})
                        return redirect('superuser_dashboard')
                    else:
                        messages.success(request, _('Welcome back, %(username)s!') % {'username': username})
                        return redirect('home')  # Buyers go to home page
                except UserProfile.DoesNotExist:
                    # If no profile exists, create one with buyer role
                    UserProfile.objects.create(user=user, phone_number='', role='buyer')
                    messages.success(request, _('Welcome back, %(username)s!') % {'username': username})
                    return redirect('home')
                
                # Check if user is Django superuser
                if user.is_superuser:
                    messages.success(request, _('Welcome back, %(username)s!') % {'username': username})
                    return redirect('superuser_dashboard')
    else:
        form = AuthenticationForm()
    
    context = {
        'form': form,
        'categories': categories,
        'cart_item_count': cart_item_count,
        'current_tab': 'login',
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/login.html', context)

def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, _('You have been logged out successfully.'))
    return redirect('home')

@login_required
def profile_view(request):
    """User profile view"""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    cart_item_count = get_cart_item_count(request)
    
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        user_profile = UserProfile.objects.create(user=request.user, phone_number='')
    
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, instance=user_profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, _('Profile updated successfully!'))
            return redirect('profile')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=user_profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'categories': categories,
        'cart_item_count': cart_item_count,
        'current_tab': 'profile',
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/profile.html', context)


@login_required
def buyer_dashboard(request):
    """Buyer dashboard view"""
    # Check if user is buyer
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'buyer':
            messages.error(request, _('Access denied. This dashboard is for buyers only.'))
            return redirect('home')
    except UserProfile.DoesNotExist:
        # Create buyer profile if doesn't exist
        UserProfile.objects.create(user=request.user, phone_number='', role='buyer')
    
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    cart_item_count = get_cart_item_count(request)
    
    # Get buyer's orders
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')[:10]
    
    # Get recent products
    recent_products = Product.objects.order_by('-created_at')[:8]
    
    context = {
        'categories': categories,
        'cart_item_count': cart_item_count,
        'orders': orders,
        'recent_products': recent_products,
        'current_tab': 'dashboard',
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/buyer_dashboard.html', context)


@login_required
def seller_dashboard(request):
    """Seller dashboard view"""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    cart_item_count = get_cart_item_count(request)
    
    # Check if user is seller
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'seller':
            messages.error(request, _('Access denied. This dashboard is for sellers only.'))
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, _('User profile not found.'))
        return redirect('home')
    
    # Get pending orders (both regular and anonymous)
    pending_orders = Order.objects.filter(status='pending').order_by('-created_at')
    anonymous_orders = Order.objects.filter(status='pending', is_anonymous=True).order_by('-created_at')
    
    # Get seller's accepted orders
    my_orders = Order.objects.filter(seller=request.user).order_by('-created_at')[:10]
    
    # Get today's report
    today = timezone.now().date()
    today_report = DailyReport.objects.filter(seller=request.user, date=today).first()
    
    context = {
        'categories': categories,
        'cart_item_count': cart_item_count,
        'pending_orders': pending_orders,
        'anonymous_orders': anonymous_orders,
        'my_orders': my_orders,
        'today_report': today_report,
        'current_tab': 'dashboard',
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/seller_dashboard.html', context)


@login_required
def superuser_dashboard(request):
    """Superuser dashboard view"""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    cart_item_count = get_cart_item_count(request)
    
    # Check if user is superuser
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'superuser' and not request.user.is_superuser:
            messages.error(request, _('Access denied. This dashboard is for administrators only.'))
            return redirect('home')
    except UserProfile.DoesNotExist:
        if not request.user.is_superuser:
            messages.error(request, _('Access denied. This dashboard is for administrators only.'))
            return redirect('home')
    
    # Get statistics
    total_users = User.objects.count()
    total_sellers = UserProfile.objects.filter(role='seller').count()
    total_buyers = UserProfile.objects.filter(role='buyer').count()
    total_orders = Order.objects.count()
    total_anonymous_orders = AnonymousOrder.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    pending_anonymous_orders = AnonymousOrder.objects.filter(is_processed=False).count()
    
    # Get recent orders
    recent_orders = Order.objects.order_by('-created_at')[:10]
    recent_anonymous_orders = Order.objects.filter(is_anonymous=True).order_by('-created_at')[:5]
    
    # Get today's reports
    today = timezone.now().date()
    today_reports = DailyReport.objects.filter(date=today).select_related('seller')
    
    # Get recent users
    recent_users = User.objects.order_by('-date_joined')[:10]
    
    context = {
        'categories': categories,
        'cart_item_count': cart_item_count,
        'total_users': total_users,
        'total_sellers': total_sellers,
        'total_buyers': total_buyers,
        'total_orders': total_orders,
        'total_anonymous_orders': total_anonymous_orders,
        'pending_orders': pending_orders,
        'pending_anonymous_orders': pending_anonymous_orders,
        'recent_orders': recent_orders,
        'recent_anonymous_orders': recent_anonymous_orders,
        'today_reports': today_reports,
        'recent_users': recent_users,
        'current_tab': 'dashboard',
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/superuser_dashboard.html', context)


@login_required
def accept_anonymous_order(request, order_id):
    """Accept an anonymous order by seller"""
    # Check if user is seller
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'seller':
            messages.error(request, _('Only sellers can accept orders.'))
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, _('User profile not found.'))
        return redirect('home')
    
    order = get_object_or_404(Order, id=order_id, status='pending', is_anonymous=True)
    order.accept_order(request.user)
    
    messages.success(request, _('Anonymous order accepted successfully!'))
    return redirect('seller_dashboard')


@login_required
def accept_order(request, order_id):
    """Accept an order by seller"""
    # Check if user is seller
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'seller':
            messages.error(request, _('Only sellers can accept orders.'))
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, _('User profile not found.'))
        return redirect('home')
    
    order = get_object_or_404(Order, id=order_id, status='pending')
    order.accept_order(request.user)
    messages.success(request, _('Order accepted successfully!'))
    return redirect('seller_dashboard')


@login_required
def complete_order(request, order_id):
    """Complete an order by seller"""
    # Check if user is seller
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'seller':
            messages.error(request, _('Only sellers can complete orders.'))
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, _('User profile not found.'))
        return redirect('home')
    
    order = get_object_or_404(Order, id=order_id, seller=request.user, status='accepted')
    order.complete_order()
    messages.success(request, _('Order completed successfully!'))
    return redirect('seller_dashboard')


@login_required
def daily_report_view(request):
    """Daily report form for sellers"""
    # Check if user is seller
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'seller':
            messages.error(request, _('Only sellers can fill daily reports.'))
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, _('User profile not found.'))
        return redirect('home')
    
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    cart_item_count = get_cart_item_count(request)
    
    # Allow filling reports for any date (including past dates)
    report_date = request.GET.get('date')
    if report_date:
        try:
            report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
        except ValueError:
            report_date = timezone.now().date()
    else:
        report_date = timezone.now().date()
    
    report, created = DailyReport.objects.get_or_create(
        seller=request.user,
        date=report_date,
        defaults={
            'books_sold_details': [],
            'books_given_free_details': [],
            'houses_visited': 0,
            'teachings_given': 0,
            'working_hours': 0,
        }
    )
    
    if request.method == 'POST':
        # Process books sold
        books_sold_details = []
        book_sold_names = request.POST.getlist('book_sold_name[]')
        custom_book_sold = request.POST.getlist('custom_book_sold[]')
        book_sold_quantities = request.POST.getlist('book_sold_quantity[]')
        
        for i, (name, custom_name, quantity) in enumerate(zip(book_sold_names, custom_book_sold, book_sold_quantities)):
            if quantity and int(quantity) > 0:
                book_name = custom_name if name == 'custom' and custom_name else name
                if book_name:
                    books_sold_details.append({
                        'book_name': book_name,
                        'quantity': int(quantity)
                    })
        
        # Process books given free
        books_given_free_details = []
        book_free_names = request.POST.getlist('book_free_name[]')
        custom_book_free = request.POST.getlist('custom_book_free[]')
        book_free_quantities = request.POST.getlist('book_free_quantity[]')
        
        for i, (name, custom_name, quantity) in enumerate(zip(book_free_names, custom_book_free, book_free_quantities)):
            if quantity and int(quantity) > 0:
                book_name = custom_name if name == 'custom' and custom_name else name
                if book_name:
                    books_given_free_details.append({
                        'book_name': book_name,
                        'quantity': int(quantity)
                    })
        
        report.books_sold_details = books_sold_details
        report.books_given_free_details = books_given_free_details
        report.houses_visited = int(request.POST.get('houses_visited', 0))
        report.teachings_given = int(request.POST.get('teachings_given', 0))
        report.working_hours = float(request.POST.get('working_hours', 0))
        report.additional_notes = request.POST.get('additional_notes', '')
        report.save()
        
        messages.success(request, _('Daily report saved successfully!'))
        return redirect('seller_dashboard')
    
    # Get available dates for dropdown (last 30 days)
    from datetime import timedelta
    available_dates = []
    for i in range(30):
        date = timezone.now().date() - timedelta(days=i)
        available_dates.append(date)
    
    # Get all products for book selection
    products = Product.objects.all().order_by('name')
    products_names = [product.name for product in products]
    
    context = {
        'categories': categories,
        'cart_item_count': cart_item_count,
        'report': report,
        'report_date': report_date,
        'available_dates': available_dates,
        'products': products,
        'products_names': products_names,
        'current_tab': 'report',
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/daily_report.html', context)


@login_required
def manage_users(request):
    """Manage users view for superuser"""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    cart_item_count = get_cart_item_count(request)
    
    # Check if user is superuser
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'superuser' and not request.user.is_superuser:
            messages.error(request, _('Access denied. Only administrators can manage users.'))
            return redirect('home')
    except UserProfile.DoesNotExist:
        if not request.user.is_superuser:
            messages.error(request, _('Access denied. Only administrators can manage users.'))
            return redirect('home')
    
    if request.method == 'POST':
        # Create new user
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')
        phone_number = request.POST.get('phone_number', '')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, _('Username already exists.'))
        elif User.objects.filter(email=email).exists():
            messages.error(request, _('Email already exists.'))
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Set superuser status if role is superuser
            if role == 'superuser':
                user.is_superuser = True
                user.is_staff = True
                user.save()
            
            UserProfile.objects.create(
                user=user,
                phone_number=phone_number,
                role=role,
                created_by=request.user
            )
            
            messages.success(request, _('User created successfully!'))
            return redirect('manage_users')
    
    # Get all users with profiles
    users = User.objects.select_related('userprofile').order_by('-date_joined')
    
    context = {
        'categories': categories,
        'cart_item_count': cart_item_count,
        'users': users,
        'current_tab': 'users',
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/manage_users.html', context)


@login_required
def view_reports(request):
    """View all reports for superuser"""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    cart_item_count = get_cart_item_count(request)
    
    # Check if user is superuser
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'superuser' and not request.user.is_superuser:
            messages.error(request, _('Access denied. Only administrators can view reports.'))
            return redirect('home')
    except UserProfile.DoesNotExist:
        if not request.user.is_superuser:
            messages.error(request, _('Access denied. Only administrators can view reports.'))
            return redirect('home')
    
    # Get filter parameters
    seller_id = request.GET.get('seller')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Build query
    reports = DailyReport.objects.select_related('seller').order_by('-date')
    
    if seller_id:
        reports = reports.filter(seller_id=seller_id)
    if date_from:
        reports = reports.filter(date__gte=date_from)
    if date_to:
        reports = reports.filter(date__lte=date_to)
    
    # Add pagination
    paginator = Paginator(reports, 20)  # Show 20 reports per page
    page_number = request.GET.get('page')
    reports = paginator.get_page(page_number)
    
    # Get sellers for filter dropdown
    sellers = User.objects.filter(userprofile__role='seller').order_by('username')
    
    context = {
        'categories': categories,
        'cart_item_count': cart_item_count,
        'reports': reports,
        'sellers': sellers,
        'current_tab': 'reports',
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/view_reports.html', context)

def password_reset_request(request):
    """Password reset request view"""
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            
            # Generate 6-digit code
            reset_code = ''.join(random.choices(string.digits, k=6))
            
            # Delete any existing reset codes for this user
            PasswordResetCode.objects.filter(user=user).delete()
            
            # Create new reset code
            reset_obj = PasswordResetCode.objects.create(
                user=user,
                reset_code=reset_code,
                expires_at=timezone.now() + timedelta(hours=1)
            )
            
            # Send email
            subject = _('Password Reset Code - Hazina ya Vitabu')
            message = _('Your password reset code is: %(code)s\n\nThis code will expire in 1 hour.') % {'code': reset_code}
            
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
            
            messages.success(request, _('Password reset code has been sent to your email.'))
            return redirect('password_reset_confirm')
            
        except User.DoesNotExist:
            messages.error(request, _('No user found with this email address.'))
    
    context = {
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/password_reset_form.html', context)

def password_reset_confirm(request):
    """Password reset confirmation view"""
    if request.method == 'POST':
        # Get the 6-digit code from separate inputs
        code_parts = []
        for i in range(1, 7):
            part = request.POST.get(f'reset_code_{i}', '')
            code_parts.append(part)
        
        reset_code = ''.join(code_parts)
        
        try:
            reset_obj = PasswordResetCode.objects.get(
                reset_code=reset_code,
                expires_at__gt=timezone.now()
            )
            
            # Store user ID in session for password reset
            request.session['reset_user_id'] = reset_obj.user.id
            reset_obj.delete()  # Delete used code
            
            return redirect('password_reset_new')
            
        except PasswordResetCode.DoesNotExist:
            messages.error(request, _('Invalid or expired reset code.'))
    
    context = {
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/password_reset_confirm.html', context)

def password_reset_new(request):
    """Set new password view"""
    if 'reset_user_id' not in request.session:
        messages.error(request, _('Invalid password reset session.'))
        return redirect('password_reset_request')
    
    if request.method == 'POST':
        password1 = request.POST.get('new_password1')
        password2 = request.POST.get('new_password2')
        
        if password1 != password2:
            messages.error(request, _('Passwords do not match.'))
        elif len(password1) < 8:
            messages.error(request, _('Password must be at least 8 characters long.'))
        else:
            try:
                user = User.objects.get(id=request.session['reset_user_id'])
                user.set_password(password1)
                user.save()
                
                del request.session['reset_user_id']
                messages.success(request, _('Password has been reset successfully. You can now log in.'))
                return redirect('login')
                
            except User.DoesNotExist:
                messages.error(request, _('Invalid user.'))
    
    context = {
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/password_reset_new.html', context)

def set_language(request, language):
    """Set user language preference"""
    if language in ['en', 'sw']:
        activate(language)
        request.session['django_language'] = language
        messages.success(request, _('Language changed successfully!'))
    return redirect(request.META.get('HTTP_REFERER', 'home'))

@require_POST
def toggle_theme(request):
    """Toggle between light and dark theme"""
    current_theme = request.session.get('theme', 'light')
    new_theme = 'dark' if current_theme == 'light' else 'light'
    request.session['theme'] = new_theme
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'theme': new_theme})
    
    return redirect(request.META.get('HTTP_REFERER', 'home'))

def get_cart_item_count(request):
    """Returns the total number of items in the user's (or anonymous user's) cart."""
    # 1) Determine the current cart, whether user or session
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user, is_ordered=False).first()
    else:
        cart_id = request.session.get('cart_id')
        cart = Cart.objects.filter(id=cart_id, is_ordered=False).first() if cart_id else None

    # 2) If no cart found, count is zero
    if not cart:
        return 0

    # 3) Sum the CartItem quantities via the 'cart_items' related name
    aggregate = cart.cart_items.aggregate(total=Sum("quantity"))
    return aggregate["total"] or 0


def About(request):
    """Displays the About page with top-level categories and their latest products."""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    category_products = {}
    for category in categories:
        # Fetch latest 4 products for each category's subcategories
        products = Product.objects.filter(category__in=category.subcategories.all()).order_by('-created_at')
        category_products[category.id] = products

    cart_item_count = get_cart_item_count(request)

    context = {
        'categories': categories,
        'category_products': category_products,
        'current_tab': 'about',
        'cart_item_count': cart_item_count,
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/about.html', context)


def Contact(request):
    """Displays the Contact page with top-level categories, their latest products, and sends a message to the superuser."""

    # Fetch categories and their subcategories along with products
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    category_products = {}
    for category in categories:
        # Fetch latest 4 products for each category's subcategories
        products = Product.objects.filter(category__in=category.subcategories.all()).order_by('-created_at')
        category_products[category.id] = products

    # Get the cart item count for the user
    cart_item_count = get_cart_item_count(request)

    if request.method == "POST":
        # Get the username and message from the form
        username = request.POST.get('username')
        message = request.POST.get('message')

        # Get the user's first name and last name, or use empty strings if not provided
        first_name = request.user.first_name if request.user.first_name else ""
        last_name = request.user.last_name if request.user.last_name else ""

        # Get the user's email
        email = request.user.email

        # Compose the email content
        subject = f"New Message from {username}"
        message_content = f"""
        Username: {username}
        First Name: {first_name}
        Last Name: {last_name}
        Email: {email}

        Message:
        {message}
        """

        # Get the superuser's email dynamically
        superuser = User.objects.filter(is_superuser=True).first()
        if superuser:
            superuser_email = superuser.email
            # Send the email to the superuser's email
            send_mail(
                subject,
                message_content,
                settings.DEFAULT_FROM_EMAIL,  # The sender's email (could be your Gmail)
                [superuser_email],  # The superuser's email (dynamically fetched)
            )

            # Show a success message
            messages.success(request, _("Your message has been sent successfully!"))
        else:
            messages.error(request, _("There was an issue sending your message. Please try again later."))

        # Redirect the user back to the contact page
        return redirect('contact')  # Adjust this URL as necessary

    # Prepare the context for rendering the page
    context = {
        'categories': categories,
        'category_products': category_products,
        'current_tab': 'contact',
        'cart_item_count': cart_item_count,
        'theme': request.session.get('theme', 'light'),
    }

    return render(request, 'users/contact.html', context)


def Faq(request):
    """Displays the FAQ page with top-level categories and their latest products."""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    category_products = {}
    for category in categories:
        # Fetch latest 4 products for each category's subcategories
        products = Product.objects.filter(category__in=category.subcategories.all()).order_by('-created_at')
        category_products[category.id] = products

    cart_item_count = get_cart_item_count(request)
    context = {
        'categories': categories,
        'category_products': category_products,
        'current_tab': 'faq',
        'cart_item_count': cart_item_count,
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/faq.html', context)


def Shop(request):
    """Displays the Shop page with all products and categories."""
    # Top-level categories with their subcategories
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')

    # Fetch the latest 20 products (or adjust slicing as you prefer)
    products = Product.objects.order_by('-created_at')[:20]

    # Get the current cart item count (handles both auth and anonymous)
    cart_item_count = get_cart_item_count(request)

    return render(request, 'users/shop.html', {
        'categories': categories,
        'products': products,
        'current_tab': 'shop',
        'cart_item_count': cart_item_count,
        'theme': request.session.get('theme', 'light'),
    })


@login_required
def generate_monthly_reports(request):
    """Generate monthly reports for all sellers"""
    # Check if user is superuser
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'superuser' and not request.user.is_superuser:
            messages.error(request, _('Access denied. Only administrators can generate reports.'))
            return redirect('home')
    except UserProfile.DoesNotExist:
        if not request.user.is_superuser:
            messages.error(request, _('Access denied. Only administrators can generate reports.'))
            return redirect('home')
    
    # Get month and year from request
    month = int(request.GET.get('month', timezone.now().month))
    year = int(request.GET.get('year', timezone.now().year))
    
    # Get all sellers
    sellers = User.objects.filter(userprofile__role='seller')
    
    generated_reports = []
    for seller in sellers:
        monthly_report = MonthlyReport.generate_monthly_report(seller, month, year)
        if monthly_report:
            generated_reports.append(monthly_report)
    
    messages.success(request, f'Generated {len(generated_reports)} monthly reports for {month}/{year}')
    return redirect('monthly_reports')

def is_superuser(user):
    """
    Allow access only to users whose profile role is 'superuser'.
    """
    try:
        return user.userprofile.role == 'superuser'
    except UserProfile.DoesNotExist:
        return False

@login_required
@user_passes_test(is_superuser)
def monthly_reports_view(request):
    """
    Display the Monthly Reports page.
    - Shows a form to pick month/year.
    - If month/year are provided via GET, loads existing MonthlyReport records.
    """
    # Current date info for form defaults
    now = timezone.now()
    current_month = now.month
    current_year = now.year

    # Build a list of years (e.g. last 5 years through this year)
    available_years = list(range(current_year - 5, current_year + 1))

    # Pull GET params if set
    month_param = request.GET.get('month')
    year_param = request.GET.get('year')

    monthly_reports = None
    selected_month = None

    if month_param and year_param:
        # Parse into integers
        month = int(month_param)
        year = int(year_param)
        # Build a date object for display heading
        selected_month = date(year, month, 1)
        # Fetch any reports already generated for that month/year
        monthly_reports = MonthlyReport.objects.filter(
            month=month,
            year=year
        ).select_related('seller')

    context = {
        'theme': request.session.get('theme', 'light'),
        'current_month': current_month,
        'current_year': current_year,
        'available_years': available_years,
        'monthly_reports': monthly_reports,
        'selected_month': selected_month,
    }

    return render(request, 'users/monthly_reports.html', context)
