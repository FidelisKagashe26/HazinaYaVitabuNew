from django import template
from django.utils.formats import number_format

register = template.Library()

@register.simple_tag
def get_products_for_category(category, category_products):
    return category_products.get(category, [])

@register.filter
def format_currency(value):
    """Formats a number as currency with 'Tsh' prefix and commas for thousands."""
    try:
        # Ensure value is a number, then format it as currency with two decimal places and commas
        value = float(value)
        formatted_value = f"{value:,.2f}"  # Format with commas and 2 decimal places
        return f"Tsh {formatted_value}/="
    except (ValueError, TypeError):
        # Handle cases where the value is not a valid number
        return "Tsh 0.00/="