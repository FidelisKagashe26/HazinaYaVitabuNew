from django.db import models
from django.contrib.auth.models import User
from django.db.models import F, Sum, DecimalField
from django.core.exceptions import ValidationError
from django.utils import timezone

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
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # Made user nullable
    is_ordered = models.BooleanField(default=False)  # Track if the cart has been converted to an order
    updated_at = models.DateTimeField(auto_now=True)  # Track last cart update time

    def total_price(self):
        # Using annotate for better performance instead of Python sum()
        total = self.items.aggregate(total=Sum(F('quantity') * F('product__price'), output_field=DecimalField()))['total']
        return total if total is not None else 0

    def __str__(self):
        return f"Cart for {self.user.username}" if self.user else "Anonymous Cart"

    def update_stock_after_checkout(self):
        """ Method to update stock after checkout process """
        for item in self.items.all():
            item.product.update_stock(item.quantity)

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)

    def clean(self):
        """Validate quantity against available stock before saving the CartItem."""
        if self.quantity > self.product.stock:
            raise ValidationError(f"Cannot add more than {self.product.stock} of {self.product.name} to the cart.")

    def save(self, *args, **kwargs):
        self.clean()  # Call clean method to validate before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} of {self.product.name}"

    @property
    def total_price(self):
        """Calculate total price for this CartItem (product price * quantity)."""
        return self.product.price * self.quantity


class Order(models.Model):
    ORDER_STATUS = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted by Seller'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_orders')
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
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order #{self.id} - {self.customer_name}"
    
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