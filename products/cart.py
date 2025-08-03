from decimal import Decimal
from django.conf import settings
from .models import Product

class Cart(object):
    def __init__(self, request):
        """Initialize the cart."""
        cart = request.session.get('cart')
        if not cart:
            cart = request.session['cart'] = {}
        self.cart = cart

    def add(self, product, quantity=1):
        """Add a product to the cart."""
        product_id = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {'quantity': 0, 'price': str(product.price)}
        self.cart[product_id]['quantity'] += quantity
        self.save()

    def __len__(self):
        """Count all items in the cart."""
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self):
        """Calculate the total price of all items in the cart."""
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())

    def save(self):
        """Save the cart to the session."""
        self.request.session['cart'] = self.cart
