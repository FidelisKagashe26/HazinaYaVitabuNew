from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal to create a UserProfile whenever a new User is created.
    """
    if created:
        # Create a UserProfile and link it to the User, only passing the required fields
        UserProfile.objects.create(
            user=instance,  # Link UserProfile to the User
            phone_number=''  # Default empty phone number, or you can add logic for this
        )

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Signal to save UserProfile whenever the associated User instance is saved.
    """
    try:
        # Attempt to save the UserProfile if it already exists
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        # If the UserProfile does not exist, create it with only required fields
        UserProfile.objects.create(
            user=instance,
            phone_number=''  # Default empty phone number, or you can add logic for this
        )
