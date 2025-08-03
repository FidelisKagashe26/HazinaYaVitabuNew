from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Category, Cart, CartItem, Order, OrderItem

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'full_hierarchy')
    search_fields = ('name', 'parent__name')
    list_filter = ('parent',)  # Filter by parent category to navigate subcategories easily

    def full_hierarchy(self, obj):
        """Display the full hierarchy of the category for better understanding."""
        hierarchy = []
        current = obj
        while current:
            hierarchy.insert(0, current.name)
            current = current.parent
        return " > ".join(hierarchy)
    full_hierarchy.short_description = 'Category Hierarchy'

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'category', 'image_preview', 'stock', 'slug', 'created_at', 'updated_at')
    list_filter = ('category', 'created_at', 'updated_at')
    search_fields = ('name', 'category__name')
    ordering = ('name',)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: auto;" />', obj.image.url)
        return "No Image"
    image_preview.short_description = 'Image Preview'

class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_ordered', 'total_price', 'updated_at')
    search_fields = ('user__username',)
    ordering = ('-updated_at',)
    list_filter = ('is_ordered',)

    def total_price(self, obj):
        """Show total price for the cart."""
        return obj.total_price()
    total_price.short_description = 'Total Price'

class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity')
    search_fields = ('cart__user__username', 'product__name')
    list_filter = ('cart', 'product')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price', 'total_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'customer_email', 'status', 'seller_name', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at', 'seller')
    search_fields = ('customer_name', 'customer_email', 'customer_phone')
    readonly_fields = ('created_at', 'accepted_at', 'completed_at')
    inlines = [OrderItemInline]
    
    def seller_name(self, obj):
        return obj.seller.username if obj.seller else 'Not Assigned'
    seller_name.short_description = 'Seller'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price', 'total_price')
    search_fields = ('order__customer_name', 'product__name')
    list_filter = ('order__status', 'product__category')
admin.site.register(Product, ProductAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(CartItem, CartItemAdmin)
