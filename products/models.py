from django.db import models
from django.contrib.auth.models import User
from django.db.models import F, Sum, DecimalField
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from django.conf import settings

class Category(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        related_name='subcategories', 
        blank=True, 
        null=True
    )  # Self-referential relationship for subcategories

    def __str__(self):
        return f"{self.parent.name} > {self.name}" if self.parent else self.name

    class Meta:
        verbose_name_plural = "Categories"  # Fix plural naming in admin
        unique_together = ('name', 'parent')  # Prevent duplicate subcategories under the same parent

class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='product_images/')  # Ensure Pillow is installed for ImageField
    description = models.TextField()
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    stock = models.PositiveIntegerField(default=0)  # To track inventory
    slug = models.SlugField(max_length=255, unique=True)  # SEO-friendly URL
    created_at = models.DateTimeField(auto_now_add=True)  # Track creation time
    updated_at = models.DateTimeField(auto_now=True)  # Track update time

    def __str__(self):
        return self.name

    def update_stock(self, quantity):
        """ Method to update stock after purchase """
        new_stock = self.stock - quantity
        if new_stock < 0:
            raise ValidationError(f"Not enough stock for {self.name}. Only {self.stock} available.")
        self.stock = new_stock
        self.save()

class Cart(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="Session key for anonymous users"
    )
    items = models.ManyToManyField(
        'Product',
        through='CartItem',
        related_name='carts'
    )
    is_ordered = models.BooleanField(
        default=False,
        help_text="Has this cart been checked out?"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time the cart was modified"
    )

    class Meta:
        unique_together = ('user', 'session_key')
        ordering = ['-updated_at']

    def total_price(self):
        """
        Compute total = sum(quantity * product.price) across all items.
        Uses a single SQL query for efficiency.
        """
        agg = self.items.through.objects.filter(cart=self).aggregate(
            total=Sum(
                F('quantity') * F('product__price'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        return agg['total'] or 0

    def __str__(self):
        if self.user:
            return f"Cart (user={self.user.username})"
        return f"Cart (session={self.session_key})"

    def update_stock_after_checkout(self):
        """
        Deduct each item's quantity from its product stock
        when the cart is converted to an order.
        """
        for cart_item in self.items.through.objects.filter(cart=self):
            product = cart_item.product
            product.stock = models.F('stock') - cart_item.quantity
            product.save(update_fields=['stock'])


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        related_name='cart_items',  # avoids clash with Cart.products
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product')

    def clean(self):
        if self.quantity > self.product.stock:
            raise ValidationError(f"Cannot add more than {self.product.stock} of {self.product.name}.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def total_price(self):
        return self.product.price * self.quantity


class Order(models.Model):
    ORDER_STATUS = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted by Seller'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_orders', null=True, blank=True)
    seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='seller_orders')
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=15)
    delivery_address = models.TextField()
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_anonymous = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        customer_type = "Anonymous" if self.is_anonymous else "Registered"
        return f"Order #{self.id} - {self.customer_name} ({customer_type})"
    
    def accept_order(self, seller):
        """Accept order by seller"""
        self.seller = seller
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save()
    
    def complete_order(self):
        """Mark order as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of order
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    @property
    def total_price(self):
        return self.price * self.quantity


class BookSaleReport(models.Model):
    """Detailed report of individual book sales by sellers"""
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='book_sales')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_sold_money = models.PositiveIntegerField(default=0, help_text="Books sold for money")
    quantity_given_free = models.PositiveIntegerField(default=0, help_text="Books given for free")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Price per book sold")
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Total revenue from this book")
    date_reported = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, help_text="Additional notes about the sale")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_reported', '-created_at']
        unique_together = ('seller', 'product', 'date_reported')
    
    def save(self, *args, **kwargs):
        # Calculate total revenue automatically
        self.total_revenue = self.sale_price * self.quantity_sold_money
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.seller.username} - {self.product.name} ({self.date_reported})"