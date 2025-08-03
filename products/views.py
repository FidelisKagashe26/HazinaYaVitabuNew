from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Product, Cart, CartItem, Category
from django.http import HttpResponseRedirect
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from .models import Cart, Category, Product
from django.shortcuts import render
from django.db.models import Sum
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

def get_cart_item_count(request):
    """Returns the total number of items in the user's (or anonymous user's) cart."""
    if request.user.is_authenticated:
        # If the user is authenticated, retrieve the cart for the user (not ordered)
        cart = Cart.objects.filter(user=request.user, is_ordered=False).first()
        
        # If the cart exists, get the total item count
        if cart:
            return cart.items.aggregate(total=Sum('quantity'))['total'] or 0
    else:
        # For anonymous users, retrieve cart from session
        cart_id = request.session.get('cart_id')
        if cart_id:
            cart = Cart.objects.filter(id=cart_id, is_ordered=False).first()
            if cart:
                return cart.items.aggregate(total=Sum('quantity'))['total'] or 0
    return 0


def Home(request):
    """Displays the homepage with top-level categories and their latest products."""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    
    # Now pass the full request object to the get_cart_item_count function
    cart_item_count = get_cart_item_count(request)

    category_products = {}
    for category in categories:
        products = Product.objects.filter(category__in=category.subcategories.all()).order_by('-created_at')
        category_products[category.id] = products

    context = {
        'current_tab': 'home',
        'categories': categories,
        'category_products': category_products,
        'cart_item_count': cart_item_count,
        'theme': request.session.get('theme', 'light'),
    }
    return render(request, 'users/landing.html', context)


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

@require_POST
def add_to_cart(request, product_id):
    """
    Adds a product to the cart or updates the quantity if already in the cart.
    Handles both authenticated and anonymous users.
    Returns the updated cart item count and total price in JSON for AJAX handling.
    """
    # Check if request is AJAX
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.user.is_authenticated:
        # For authenticated users, get or create cart
        cart, created = Cart.objects.get_or_create(user=request.user, is_ordered=False)
    else:
        # For anonymous users, use session-based cart
        cart_id = request.session.get('cart_id')
        if not cart_id:
            cart = Cart.objects.create()
            request.session['cart_id'] = cart.id
        else:
            cart = get_object_or_404(Cart, id=cart_id)

    # Retrieve the product
    product = get_object_or_404(Product, id=product_id)

    # Validate quantity from request
    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            error_msg = _("Quantity must be at least 1.")
            if is_ajax:
                return JsonResponse({"error": error_msg, "success": False}, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('product_detail', pk=product_id)
    except (ValueError, TypeError):
        error_msg = _("Invalid quantity specified.")
        if is_ajax:
            return JsonResponse({"error": error_msg, "success": False}, status=400)
        else:
            messages.error(request, error_msg)
            return redirect('product_detail', pk=product_id)

    # Check if the product is already in the cart
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)

    # Validate stock availability
    if product.stock >= cart_item.quantity + quantity:
        if not created:
            cart_item.quantity += quantity  # Update the quantity for existing item
        else:
            cart_item.quantity = quantity  # Set the quantity for a new item
        cart_item.save()

        # Get updated cart item count and total
        cart_item_count = cart.items.aggregate(total=Sum('quantity'))['total'] or 0
        cart_total = cart.total_price()

        success_msg = _("%(product)s has been added to your cart! (Quantity: %(quantity)d)") % {
            'product': product.name, 
            'quantity': cart_item.quantity
        }
        
        if is_ajax:
            # Return updated information for AJAX requests
            return JsonResponse({
                "message": success_msg,
                "cart_item_count": cart_item_count,
                "cart_total": f"Tsh {cart_total:.2f}",
                "success": True
            })
        else:
            # For regular form submissions
            messages.success(request, success_msg)
            return redirect('product_detail', pk=product_id)
    else:
        error_msg = _("Only %(stock)d units of %(product)s are available.") % {
            'stock': product.stock, 
            'product': product.name
        }
        
        if is_ajax:
            return JsonResponse({
                "error": error_msg,
                "success": False
            }, status=400)
        else:
            messages.error(request, error_msg)
            return redirect('product_detail', pk=product_id)


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import Cart, CartItem, Category


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

from django.shortcuts import render, redirect
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.template.loader import render_to_string
from .models import Cart, CartItem, Category, Product, Order, OrderItem
from .models import Cart, CartItem, Product, Category, Order, OrderItem

def place_order(request):
    """Handles the Place Order process, creates Order record, and sends emails with product images embedded."""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    
    # For authenticated users, retrieve or create cart
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        # For anonymous users, handle cart using session
        cart_id = request.session.get('cart_id')
        if cart_id:
            cart = Cart.objects.filter(id=cart_id).first()
        else:
            cart = None
    
    if cart:
        cart_items = CartItem.objects.filter(cart=cart)
    else:
        cart_items = []

    # For category products
    category_products = {}
    for category in categories:
        products = Product.objects.filter(category__in=category.subcategories.all()).order_by('-created_at')
        category_products[category.id] = products
        
    if not cart_items:
        return redirect('shop')
    
    if request.method == 'POST':
        # Retrieve data from the form
        city = request.POST.get('city')
        address = request.POST.get('address')
        email = request.POST.get('email')
        phone = request.POST.get('phone')

        # Calculate the total price for each product and the grand total
        grand_total = 0
        calculated_items = []
        for item in cart_items:
            total_price = item.product.price * item.quantity
            grand_total += total_price
            calculated_items.append({
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price": item.product.price,
                "total_price": total_price,
                "image_name": item.product.image.name,
                "image_url": item.product.image.url,
            })
        
        # Create Order record
        order = Order.objects.create(
            customer=request.user if request.user.is_authenticated else None,
            customer_name=city,
            customer_email=email,
            customer_phone=phone,
            delivery_address=address,
            total_amount=grand_total,
            status='pending'
        )
        
        # Create OrderItems
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )
        
        # Prepare the HTML message body with cart data for the customer
        html_content = render_to_string(
            'products/order_email_template.html',
            {
                "calculated_items": calculated_items,  # Pass the calculated items
                "user": request.user,
                "grand_total": grand_total,
                "customer_phone": phone,  # Use phone from form
                "username": city,
                "address": address,
                "order_id": order.id,
            }
        )

        # Create the email with embedded images for the customer
        email_message = EmailMultiAlternatives(
            subject=f"Order Confirmation - Order #{order.id}",
            body="Your order has been successfully placed.",
            from_email="fmklinkcompany@gmail.com",
            to=[email],  # Use the email from the form
        )
        email_message.attach_alternative(html_content, "text/html")

        # Embed product images as MIME images
        for item in calculated_items:
            with open(item["image_url"][1:], 'rb') as img_file:  # Adjust to strip leading slash from image URL
                email_message.attach(
                    item["image_name"],
                    img_file.read(),
                    'image/jpeg'
                )
                html_content = html_content.replace(
                    item["image_url"],
                    f'cid:{item["image_name"]}'  # Use CID to embed image in email
                )
        email_message.attach_alternative(html_content, "text/html")

        # Send the email to the customer
        email_message.send()

        # Notify the superuser about the order with form data
        superusers = User.objects.filter(is_superuser=True)
        if superusers.exists():
            admin_emails = [user.email for user in superusers if user.email]
            if admin_emails:
                admin_subject = f"New Order #{order.id} from {request.user.username if request.user.is_authenticated else 'Anonymous'}"

                # Prepare the admin email message
                admin_message = render_to_string(
                    'products/admin_order_notification.html',
                    {
                        "user": request.user,
                        "calculated_items": calculated_items,
                        "grand_total": grand_total,
                        "customer_phone": phone,  # Pass the phone from form
                        "username": city,  # City from form
                        "email": email,
                        "address": address,  # Address from form
                        "order_id": order.id,
                    }
                )

                # Create the admin email
                admin_email_message = EmailMessage(
                    subject=admin_subject,
                    body=admin_message,
                    from_email="fideliskagashe@gmail.com",
                    to=admin_emails,
                )

                # Attach product images to the admin email
                for item in calculated_items:
                    with open(item["image_url"][1:], 'rb') as img_file:
                        admin_email_message.attach(
                            item["image_name"],
                            img_file.read(),
                            'image/jpeg'
                        )
                        admin_message = admin_message.replace(
                            item["image_url"],
                            f'cid:{item["image_name"]}'  # Embed images in the email
                        )
                
                admin_email_message.content_subtype = "html"
                admin_email_message.send()

        # Clear the cart after sending the order confirmation
        if cart:
            cart_items.delete()

        # Render the confirmation page
        return render(request, 'products/order_confirmation.html',
                       {"grand_total": grand_total,
                        "calculated_items": calculated_items,
                        "order_id": order.id,
                        'categories': categories,
                        'category_products': category_products,
                        'theme': request.session.get('theme', 'light'),
                        })
    else:
        # If the request is not POST, return the order page
        return render(request, 'products/place_order.html', {
            'categories': categories,
            'category_products': category_products,
            'cart_item_count': get_cart_item_count(request),  # assuming you have a get_cart_item_count utility function
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

def update_cart(request, product_id):
    """Updates the quantity of a product in the cart."""
    if request.method == "POST":
        # Ensure the user has a cart
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        # Retrieve the product and validate the quantity
        product = get_object_or_404(Product, id=product_id)
        try:
            new_quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            messages.error(request, "Invalid quantity entered.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', 'view_cart'))

        if new_quantity < 1:
            messages.error(request, "Quantity must be at least 1.")
        else:
            # Retrieve the cart item and update its quantity
            cart_item = CartItem.objects.filter(cart=cart, product=product).first()
            if cart_item:
                if product.stock >= new_quantity:
                    cart_item.quantity = new_quantity
                    cart_item.save()
                    messages.success(request, f"Updated quantity for {product.name} to {new_quantity}.")
                else:
                    messages.error(request, f"Not enough stock for {product.name}. Only {product.stock} available.")
            else:
                messages.error(request, f"{product.name} not found in your cart.")

    # Redirect to the previous page (view_cart in this case)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', 'view_cart'))
