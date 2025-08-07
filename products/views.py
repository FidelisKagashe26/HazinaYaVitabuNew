from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Product, Cart, CartItem, Category
from users.models import AnonymousOrder
from django.http import HttpResponseRedirect
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from .models import Cart, Category, Product
from django.shortcuts import render
from django.db.models import Sum
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator


def get_cart_item_count(request):
    """Returns the total number of items in the user's (or anonymous user's) cart."""
    # 1) Authenticated users
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user, is_ordered=False).first()
    else:
        # 2) Anonymous users: id stored in session
        cart_id = request.session.get('cart_id')
        cart = Cart.objects.filter(id=cart_id, is_ordered=False).first() if cart_id else None

    if not cart:
        return 0

    # 3) Sum over CartItem.quantity via the 'cart_items' related name
    agg = cart.cart_items.aggregate(total=Sum('quantity'))
    return agg['total'] or 0


def Home(request):
    """Displays the homepage with top-level categories and their latest products."""
    # Top-level categories
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')

    # Cart badge count
    cart_item_count = get_cart_item_count(request)

    # Latest products per category
    category_products = {}
    for category in categories:
        subs = category.subcategories.all()
        qs = Product.objects.filter(category__in=subs).order_by('-created_at')
        category_products[category] = qs

    return render(request, 'users/landing.html', {
        'current_tab': 'home',
        'categories': categories,
        'category_products': category_products,
        'cart_item_count': cart_item_count,
        'theme': request.session.get('theme', 'light'),
    })


def product_list(request):
    """Displays the list of all products."""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    products = Product.objects.all()
    cart_item_count = get_cart_item_count(request.user)

    context = {
        'products': products,
        'current_tab': 'shop',
        'categories': categories,
        'cart_item_count': cart_item_count,
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'products/product_list.html', context)


# Import necessary modules
from .models import Product, Category
from django.shortcuts import render, get_object_or_404

def product_detail(request, pk):
    """Displays the details of a single product."""
    product = get_object_or_404(Product, pk=pk)
    categories = Category.objects.filter(parent__isnull=True)
    
    # Get cart item count using the utility function
    cart_item_count = get_cart_item_count(request)

    return render(request, 'products/product_detail.html', {
        'product': product,
        'current_tab': 'shop',
        'categories': categories,
        'cart_item_count': cart_item_count,
        'theme': request.session.get('theme', 'light'),
    })

def products_by_subcategory(request, subcategory_name):
    """Displays products filtered by a subcategory, with additional search and price range filters."""
    # Get the subcategory based on its name
    subcategory = get_object_or_404(Category, name=subcategory_name)
    products = Product.objects.filter(category=subcategory)
    
    # Apply product name filter
    product_name = request.GET.get('product_name', '')
    if product_name:
        products = products.filter(name__icontains=product_name)

    # Apply price range filter
    price_range = request.GET.get('price_range', '')
    if price_range:
        price_ranges = {
            "1": (0, 1000),
            "2": (1000, 5000),
            "3": (5000, 10000),
            "4": (10000, 20000),
            "5": (20000, 50000),
            "6": (50000, 100000),
            "7": (100000, 200000),
            "8": (200000, 500000),
            "9": (500000, 700000),
            "10": (700000, 1000000),
            "11": (1000000, float('inf'))
        }
        if price_range in price_ranges:
            min_price, max_price = price_ranges[price_range]
            products = products.filter(price__gte=min_price, price__lte=max_price)

    # Fetch all categories for the navigation
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')

    # Get cart item count (using the utility function)
    cart_item_count = get_cart_item_count(request)

    # Pass all necessary data to the template
    return render(request, 'products/product_list.html', {
        'products': products,
        'current_tab': 'shop',
        'categories': categories,
        'subcategory_name': subcategory_name,
        'cart_item_count': cart_item_count,
        'theme': request.session.get('theme', 'light'),
    })

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Cart, CartItem, Product


from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Cart, CartItem, Product
from django.db.models import Sum


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import Cart, CartItem, Category

@require_POST
def add_to_cart(request, product_id):
    """
    Adds a product to the cart (or updates its quantity).
    Works for both authenticated and anonymous users.
    Returns JSON for AJAX; otherwise redirects with Django messages.
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # ─── 1) Determine/create the cart ─────────────────────────────────────
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(
            user=request.user,
            session_key=None,
            is_ordered=False
        )
    else:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(
            user=None,
            session_key=session_key,
            is_ordered=False
        )
        request.session['cart_id'] = cart.id

    # ─── 2) Fetch the product ────────────────────────────────────────────
    product = get_object_or_404(Product, id=product_id)

    # ─── 3) Parse & validate requested quantity ──────────────────────────
    try:
        added_qty = int(request.POST.get('quantity', 1))
        if added_qty < 1:
            raise ValueError
    except (ValueError, TypeError):
        error_msg = "Please enter a valid quantity (minimum 1)."
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('product_detail', pk=product_id)

    # ─── 4) Get or create the CartItem ───────────────────────────────────
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)

    # ─── 5) Check stock and update quantity ──────────────────────────────
    new_quantity = (cart_item.quantity + added_qty) if not created else added_qty
    if new_quantity > product.stock:
        error_msg = f"Only {product.stock} unit(s) of {product.name} available."
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('product_detail', pk=product_id)

    cart_item.quantity = new_quantity
    cart_item.save()

    # ─── 6) Recalculate totals ───────────────────────────────────────────
    total_items = cart.cart_items.aggregate(total=Sum('quantity'))['total'] or 0
    total_price = cart.total_price()

    success_msg = f"{product.name} added to cart. You now have {total_items} item(s)."

    if is_ajax:
        return JsonResponse({
            'success': True,
            'message': success_msg,
            'cart_item_count': total_items,
            'cart_total': f"Tsh {total_price:.2f}"
        })
    messages.success(request, success_msg)
    return redirect('product_detail', pk=product_id)


from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from .models import Cart, CartItem, Category

def view_cart(request):
    """Displays the cart with all items and total sum."""
    if request.user.is_authenticated:
        # For authenticated users
        cart, created = Cart.objects.get_or_create(user=request.user, is_ordered=False)
    else:
        # For anonymous users
        cart_id = request.session.get('cart_id')
        if not cart_id:
            cart = Cart.objects.create()
            request.session['cart_id'] = cart.id
        else:
            cart = get_object_or_404(Cart, id=cart_id)

    # Retrieve cart items
    cart_items = CartItem.objects.filter(cart=cart)

    # Calculate total item count (sum of quantities)
    cart_item_count = cart_items.aggregate(total=Sum('quantity'))['total'] or 0

    # Calculate the total sum for the cart
    total_sum = cart.total_price()

    # Fetch categories (assuming a parent-child relationship)
    categories = Category.objects.filter(parent__isnull=True)

    # Return the rendered cart view
    return render(request, 'products/cart.html', {
        'cart_items': cart_items,
        'categories': categories,
        'total_sum': total_sum,
        'current_tab': 'cart',
        'current_tab': 'shop',
        'cart_item_count': cart_item_count,
        'cart': cart,
        'theme': request.session.get('theme', 'light'),
    })


from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CartItem


from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from .models import Cart, CartItem

def remove_from_cart(request, pk):
    """Removes an item from the logged-in user's or anonymous user's cart."""
    try:
        if request.user.is_authenticated:
            # For authenticated users, get the cart for the user
            cart_item = get_object_or_404(CartItem, pk=pk, cart__user=request.user)
        else:
            # For anonymous users, retrieve the cart from the session
            cart_id = request.session.get('cart_id')
            if not cart_id:
                messages.error(request, 'No cart found for anonymous user.')
                return redirect('view_cart')

            cart = get_object_or_404(Cart, id=cart_id)
            cart_item = get_object_or_404(CartItem, pk=pk, cart=cart)

        # Delete the cart item
        cart_item.delete()

        # Send success message
        messages.success(request, f'Item "{cart_item.product.name}" removed from cart.')

    except CartItem.DoesNotExist:
        # In case the cart item does not exist, send an error message
        messages.error(request, 'This item could not be found in your cart.')

    return redirect('view_cart')


from django.shortcuts import render, redirect, get_object_or_404
from .models import Cart, CartItem, Category

def checkout(request):
    """Displays the checkout page with cart items and total price."""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    
    if request.user.is_authenticated:
        # For authenticated users, get or create the cart associated with the user
        cart, created = Cart.objects.get_or_create(user=request.user, is_ordered=False)
        
        # Get user profile for pre-filling form
        try:
            user_profile = request.user.userprofile
        except UserProfile.DoesNotExist:
            user_profile = None
    else:
        # For anonymous users, retrieve the cart from the session
        cart_id = request.session.get('cart_id')
        if not cart_id:
            # If no cart exists, create a new one and store the cart_id in the session
            cart = Cart.objects.create()
            request.session['cart_id'] = cart.id
        else:
            cart = get_object_or_404(Cart, id=cart_id)
        user_profile = None

    # Retrieve cart items for the cart
    cart_items = CartItem.objects.filter(cart=cart)

    # Calculate total sum (total price of all items in the cart)
    total_sum = sum(item.product.price * item.quantity for item in cart_items)

    # Calculate total cart item count (sum of all item quantities)
    cart_item_count = sum(item.quantity for item in cart_items)

    # Return the rendered checkout page with context data
    return render(request, 'products/checkout.html', {
        'cart_items': cart_items,
        'categories': categories,
        'total_sum': total_sum,
        'current_tab': 'shop',
        'cart_item_count': cart_item_count,
        'user_profile': user_profile,
        'theme': request.session.get('theme', 'light'),
    })


from django.conf import settings
from django.core.mail import EmailMessage
from django.contrib.auth.models import User


from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.template.loader import render_to_string
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.html import escape
from users.models import UserProfile
import logging


# Set up logging
logger = logging.getLogger(__name__)


from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.shortcuts import render, redirect
from .models import Cart, CartItem, Category, Product
from django.contrib.auth.models import User

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.shortcuts import render, redirect, get_object_or_404
from .models import Cart, CartItem, Category, Product, Order, OrderItem
from django.contrib.auth.models import User
from decimal import Decimal
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.shortcuts import render, redirect
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.template.loader import render_to_string
from .models import Cart, CartItem, Category, Product, Order, OrderItem
from .models import Cart, CartItem, Product, Category, Order, OrderItem

@require_http_methods(["GET", "POST"])
@transaction.atomic
def place_order(request):
    """
    Handles order placement:
     - Builds cart items list
     - Computes totals
     - Creates Order or AnonymousOrder + items
     - Sends confirmation emails (customer + admins) with embedded images
     - Clears cart
    """
    # Fetch categories for sidebar/nav
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    category_products = {
        cat.id: Product.objects.filter(category__in=cat.subcategories.all()).order_by('-created_at')[:10]
        for cat in categories
    }

    # Identify the active cart
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user, is_ordered=False).first()
    else:
        cart_id = request.session.get('cart_id')
        cart = Cart.objects.filter(id=cart_id, is_ordered=False).first() if cart_id else None

    if not cart or not cart.cart_items.exists():
        messages.warning(request, _("Your cart is empty."))
        return redirect('shop')

    if request.method == 'GET':
        return render(request, 'products/place_order.html', {
            'categories': categories,
            'category_products': category_products,
            'cart_item_count': cart.cart_items.aggregate(total=Sum('quantity'))['total'] or 0,
            'theme': request.session.get('theme', 'light'),
        })

    # POST: collect form data
    name    = request.POST.get('name', '').strip()
    email   = request.POST.get('email', '').strip()
    phone   = request.POST.get('phone', '').strip()
    address = request.POST.get('address', '').strip()

    # Build items list and grand total
    calculated_items = []
    grand_total = Decimal('0.00')
    for item in cart.cart_items.select_related('product'):
        unit_price = item.product.price
        line_total = unit_price * item.quantity
        grand_total += line_total
        calculated_items.append({
            'product_id':   item.product.id,
            'name':         item.product.name,
            'quantity':     item.quantity,
            'unit_price':   float(unit_price),
            'line_total':   float(line_total),
            'image_name':   item.product.image.name,
            'image_path':   item.product.image.path,
        })

    # Create order record
    if request.user.is_authenticated:
        order = Order.objects.create(
            customer=request.user,
            customer_name=name,
            customer_email=email,
            customer_phone=phone,
            delivery_address=address,
            total_amount=grand_total,
            is_anonymous=False
        )
        for data in calculated_items:
            OrderItem.objects.create(
                order=order,
                product_id=data['product_id'],
                quantity=data['quantity'],
                price=Decimal(str(data['unit_price']))
            )
    else:
        # Create a regular Order for anonymous users too
        order = Order.objects.create(
            customer=None,
            customer_name=name,
            customer_email=email,
            customer_phone=phone,
            delivery_address=address,
            total_amount=grand_total,
            is_anonymous=True
        )
        for data in calculated_items:
            OrderItem.objects.create(
                order=order,
                product_id=data['product_id'],
                quantity=data['quantity'],
                price=Decimal(str(data['unit_price']))
            )

    # Mark cart ordered and clear session
    cart.is_ordered = True
    cart.save(update_fields=['is_ordered'])
    request.session.pop('cart_id', None)

    # Prepare email context
    email_ctx = {
        'order':          order,
        'items':          calculated_items,
        'grand_total':    grand_total,
        'customer_name':  name,
        'address':        address,
    }

    # Send customer confirmation
    subject = _("Order Confirmation #%s") % order.id
    html_body = render_to_string('products/order_email_template.html', email_ctx)
    msg = EmailMultiAlternatives(subject, '', to=[email])
    msg.attach_alternative(html_body, 'text/html')
    for itm in calculated_items:
        with open(itm['image_path'], 'rb') as img:
            msg.attach(itm['image_name'], img.read(), 'image/jpeg')
            html_body = html_body.replace(
                itm['image_name'], f"cid:{itm['image_name']}"
            )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=True)

    # Notify admins
    admin_emails = list(
        User.objects.filter(is_superuser=True, email__isnull=False)
                    .values_list('email', flat=True)
    )
    if admin_emails:
        admin_ctx = {**email_ctx, 'is_anonymous': not request.user.is_authenticated}
        admin_html = render_to_string('products/admin_order_notification.html', admin_ctx)
        admin_msg = EmailMessage(
            _("New Order #%s") % order.id, admin_html, to=admin_emails
        )
        admin_msg.content_subtype = 'html'
        for itm in calculated_items:
            with open(itm['image_path'], 'rb') as img:
                admin_msg.attach(itm['image_name'], img.read(), 'image/jpeg')
                admin_html = admin_html.replace(
                    itm['image_name'], f"cid:{itm['image_name']}"
                )
        admin_msg.send(fail_silently=True)

    # Finally, render confirmation page
    return render(request, 'products/order_confirmation.html', {
        'order': order,
        'items': order.items.all(),
        'grand_total': grand_total,
        'categories': categories,
        'category_products': category_products,
        'theme': request.session.get('theme', 'light'),
    })

from django.contrib import messages
from django.shortcuts import redirect
from django.core.exceptions import ValidationError

def process_payment(request):
    """Processes the payment and updates stock and order status."""
    try:
        # Get the cart for the user
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_items = CartItem.objects.filter(cart=cart)

        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('shop')

        # Update stock after checkout and set the order as placed
        cart.update_stock_after_checkout()
        cart.is_ordered = True
        cart.save()

        # Clear the cart items after successful payment
        cart_items.delete()

        # Notify the user that the payment was successful
        messages.success(request, 'Payment processed successfully! Your order is confirmed.')

        # Redirect the user to the order confirmation page
        return redirect('order_confirmation')  # Change to your actual confirmation page view name

    except ValidationError as e:
        # If there is an issue updating stock (e.g., not enough stock), show an error message
        messages.error(request, f"Error: {e.message}")
        return redirect('view_cart')

    except Exception as e:
        # Catch any other unexpected errors
        messages.error(request, f"An error occurred while processing your payment: {str(e)}")
        return redirect('view_cart')


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from .models import Cart, CartItem, Product

# views.py

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from .models import Cart, CartItem, Product

def update_cart(request, product_id):
    """Updates the quantity of a product in the cart for both logged-in and anonymous users."""
    if request.method != "POST":
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "view_cart"))

    # 1) Identify or create the active cart
    if request.user.is_authenticated:
        qs = Cart.objects.filter(
            user=request.user,
            session_key__isnull=True,
            is_ordered=False
        )
        cart = qs.first()
        if not cart:
            cart = Cart.objects.create(user=request.user, is_ordered=False)
    else:
        # ensure session exists
        if not request.session.session_key:
            request.session.create()
        skey = request.session.session_key

        qs = Cart.objects.filter(
            user__isnull=True,
            session_key=skey,
            is_ordered=False
        )
        cart = qs.first()
        if not cart:
            cart = Cart.objects.create(session_key=skey, is_ordered=False)
        request.session['cart_id'] = cart.id

    # 2) Fetch product and parse new quantity
    product = get_object_or_404(Product, id=product_id)
    try:
        new_qty = int(request.POST.get("quantity", 1))
        if new_qty < 1:
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, "Please enter a valid quantity (1 or more).")
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "view_cart"))

    # 3) Load the cart item
    cart_item = CartItem.objects.filter(cart=cart, product=product).first()
    if not cart_item:
        messages.error(request, f"{product.name} is not in your cart.")
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "view_cart"))

    # 4) Check stock
    if new_qty > product.stock:
        messages.error(
            request,
            f"Not enough stock for {product.name}. Only {product.stock} available."
        )
    else:
        cart_item.quantity = new_qty
        cart_item.save()
        messages.success(
            request,
            f"Updated {product.name} quantity to {new_qty}."
        )

    # 5) Redirect back
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "view_cart"))