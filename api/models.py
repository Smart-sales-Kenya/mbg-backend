from django.db import models
import uuid
import random
import string
from django.utils import timezone


def generate_unique_id():
    """Generate a unique 6-character alphanumeric ID for events"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(random.choices(alphabet, k=6))


class ContactMessage(models.Model):
    SUBJECT_CHOICES = [
        ('program', 'Program Inquiry'),
        ('recruitment', 'Recruitment'),
        ('partnership', 'Partnership'),
        ('general', 'General Inquiry'),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.subject}"


class TeamMember(models.Model):
    ROLE_CHOICES = [
        ('leadership', 'Leadership'),
        ('support', 'Support Team'),
    ]

    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=ROLE_CHOICES)
    image = models.ImageField(upload_to='team/')
    bio = models.TextField()
    email = models.EmailField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class GalleryCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "Gallery Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class GalleryItem(models.Model):
    category = models.ForeignKey(GalleryCategory, on_delete=models.CASCADE, related_name='items')
    image = models.ImageField(upload_to='gallery/', blank=True, null=True)
    video_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.category.name} - Item"


class Testimonial(models.Model):
    author = models.CharField(max_length=100)
    company = models.CharField(max_length=150)
    text = models.TextField(max_length=500)
    logo = models.ImageField(upload_to='testimonials/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author} - {self.company}"

from django.utils import timezone

class Event(models.Model):
    EVENT_STATUS_CHOICES = [
        ('open', 'Open for Registration'),
        ('closed', 'Closed'),
        ('invite', 'Invite Only'),
        ('early_bird', 'Early Bird Available'),
        ('completed', 'Completed'),
    ]

    CATEGORY_CHOICES = [
        ('popular', 'Popular'),
        ('online', 'Online'),
        ('special', 'Special Event'),
        ('intensive', 'Intensive'),
        ('regular', 'Regular'),
    ]

    # Basic Information
    id = models.CharField(primary_key=True, max_length=6, editable=False, default=generate_unique_id)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=255, blank=True, default='')
    tagline = models.CharField(max_length=255, blank=True, default='')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True)
    
    # Date and Time
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    # Location and Details
    location = models.CharField(max_length=255)
    participants_limit = models.PositiveIntegerField()
    duration = models.CharField(max_length=100, blank=True)
    description = models.TextField()

    # Pricing
    investment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='KES')
    is_free = models.BooleanField(default=False)

    # Status
    status = models.CharField(max_length=50, choices=EVENT_STATUS_CHOICES)
    registration_open = models.BooleanField(default=True)
    
    # Media
    image = models.ImageField(upload_to='events/', blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        return self.title

    @property
    def available_spots(self):
        """Calculate available spots for registration"""
        registered_count = self.registrations.filter(
            registration_status__in=['pending', 'confirmed']
        ).count()
        return max(0, self.participants_limit - registered_count)

    @property
    def is_available_for_registration(self):
        """Check if event can accept new registrations"""
        return (self.registration_open and 
                self.status == 'open' and 
                self.available_spots > 0)


class EventRegistration(models.Model):
    EXPERIENCE_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    HEARD_ABOUT_CHOICES = [
        ('social_media', 'Social Media'),
        ('email', 'Email Newsletter'),
        ('friend', 'Friend/Colleague'),
        ('website', 'Website'),
        ('other', 'Other'),
    ]

    REGISTRATION_STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('waiting_list', 'Waiting List'),
    ]

    # Event relationship
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    
    # Personal Information
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    # Professional Information
    company = models.CharField(max_length=100)
    job_title = models.CharField(max_length=100)
    industry = models.CharField(max_length=100, blank=True)
    experience_level = models.CharField(max_length=50, choices=EXPERIENCE_CHOICES, blank=True)
    goals = models.TextField(blank=True)
    heard_about = models.CharField(max_length=50, choices=HEARD_ABOUT_CHOICES, blank=True)

    # Registration Status
    registration_status = models.CharField(
        max_length=20, 
        choices=REGISTRATION_STATUS_CHOICES, 
        default='pending'
    )
    
    # Timestamps
    registration_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-registration_date']
        unique_together = ['event', 'email']

    def __str__(self):
        return f"{self.full_name} - {self.event.title}"

    @property
    def requires_payment(self):
        """Check if this registration requires payment"""
        return not self.event.is_free

    @property
    def is_confirmed(self):
        """Check if registration is fully confirmed"""
        if self.event.is_free:
            return self.registration_status == 'confirmed'
        return self.registration_status == 'confirmed'

    def confirm_registration(self):
        """Mark registration as confirmed"""
        self.registration_status = 'confirmed'
        self.save()

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('pesapal', 'PesaPal'),
        ('cash', 'Cash'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    # Unique identifier
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to registration
    registration = models.OneToOneField(
        EventRegistration,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    
    # Payment Details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # PesaPal Fields - ADD null=True TO ALL
    pesapal_order_tracking_id = models.CharField(max_length=50, blank=True, null=True)
    pesapal_transaction_id = models.CharField(max_length=50, blank=True, null=True)
    pesapal_merchant_reference = models.CharField(max_length=100, blank=True, null=True)
    pesapal_payment_url = models.URLField(blank=True, null=True)
    
    # Timestamps
    payment_initiated_at = models.DateTimeField(null=True, blank=True)
    payment_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Customer Info
    description = models.TextField(blank=True)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pesapal_order_tracking_id']),
            models.Index(fields=['payment_status']),
        ]

    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        # Auto-populate from event registration
        if self.registration:
            if not self.amount:
                self.amount = self.registration.event.investment_amount or 0
            if not self.currency:
                self.currency = self.registration.event.currency
            if not self.customer_email:
                self.customer_email = self.registration.email
            if not self.customer_phone:
                self.customer_phone = self.registration.phone
            if not self.description:
                self.description = f"Event: {self.registration.event.title}"
        
        # Ensure PesaPal fields have default values if empty
        if not self.pesapal_merchant_reference:
            self.pesapal_merchant_reference = f"MBG-{self.registration.id}"
        
        super().save(*args, **kwargs)

    def mark_as_completed(self, transaction_id=None):
        """Mark payment as completed and confirm registration"""
        self.payment_status = 'completed'
        self.payment_completed_at = timezone.now()
        if transaction_id:
            self.pesapal_transaction_id = transaction_id
        self.save()
        
        # Auto-confirm the linked registration
        self.registration.registration_status = 'confirmed'
        self.registration.save()
        

    @property
    def is_successful(self):
        """Check if payment was successful"""
        return self.payment_status == 'completed'

class ProgramCategory(models.Model):
    """Categories of programs: Training, Enablement, Events"""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)

    class Meta:
        verbose_name_plural = "Program Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Program(models.Model):
    """General program model that works for all program types"""
    id = models.CharField(
        primary_key=True,
        max_length=6,
        editable=False,
        default=generate_unique_id
    )    
    category = models.ForeignKey(ProgramCategory, on_delete=models.CASCADE, related_name="programs")
    title = models.CharField(max_length=200)
    duration = models.CharField(max_length=50)
    price = models.CharField(max_length=50)
    description = models.TextField()
    focus = models.TextField(blank=True,default='')
    outcome = models.TextField(blank=True,default='')
    skills = models.TextField(blank=True,default='')
    format = models.TextField(blank=True,default='')
    badge = models.CharField(max_length=50, blank=True,default='OpenBook')

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} ({self.category.name})"


class ProgramFeature(models.Model):
    """Features of a program"""
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="features")
    description = models.CharField(max_length=255)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.program.title} - {self.description[:30]}"


class ProgramRegistration(models.Model):
    """Stores registration details for any Program"""
    TEAM_SIZE_CHOICES = [
        ("1-5", "1-5 people"),
        ("5-10", "5-10 people"),
        ("10-20", "10-20 people"),
        ("20+", "20+ people"),
    ]

    # Program relationship
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='registrations')

    # Personal Information
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)

    # Professional Information
    company_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=255, blank=True)
    team_size = models.CharField(max_length=10, choices=TEAM_SIZE_CHOICES, blank=True)

    # Additional Information
    challenges = models.TextField(blank=True, help_text="Describe your current challenges and goals")

    # Payment
    has_paid = models.BooleanField(default=False)
    # payment_reference = models.CharField(max_length=255, blank=True)

    # Timestamps
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-registered_at']

    def __str__(self):
        return f"{self.full_name} - {self.program.title}"
    
    
# models.py
from decimal import Decimal, InvalidOperation
class ProgramPayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('pesapal', 'PesaPal'),
        ('cash', 'Cash'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.OneToOneField(
        'ProgramRegistration',
        on_delete=models.CASCADE,
        related_name='payment'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # PesaPal Fields
    pesapal_order_tracking_id = models.CharField(max_length=50, blank=True, null=True)
    pesapal_transaction_id = models.CharField(max_length=50, blank=True, null=True)
    pesapal_merchant_reference = models.CharField(max_length=100, blank=True, null=True)
    pesapal_payment_url = models.URLField(blank=True, null=True)
    
    # Timestamps
    payment_initiated_at = models.DateTimeField(null=True, blank=True)
    payment_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Customer Info
    description = models.TextField(blank=True)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pesapal_order_tracking_id']),
            models.Index(fields=['payment_status']),
        ]

    def __str__(self):
        return f"ProgramPayment {self.id} - {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        # Auto-populate from program registration
        if self.registration:
            if not self.amount:
                # Parse program price to decimal
                try:
                    price_str = self.registration.program.price.replace('KES', '').replace(',', '').strip()
                    self.amount = Decimal(price_str)
                except (ValueError, InvalidOperation):
                    self.amount = Decimal('0')
            
            if not self.currency:
                self.currency = 'KES'
                
            if not self.customer_email:
                self.customer_email = self.registration.email
                
            if not self.customer_phone:
                self.customer_phone = self.registration.phone_number
                
            if not self.description:
                self.description = f"Program: {self.registration.program.title}"
        
        if not self.pesapal_merchant_reference:
            self.pesapal_merchant_reference = f"MBG-PRG-{self.registration.id}"
        
        super().save(*args, **kwargs)

    def mark_as_completed(self, transaction_id=None):
        self.payment_status = 'completed'
        self.payment_completed_at = timezone.now()
        if transaction_id:
            self.pesapal_transaction_id = transaction_id
        self.save()
        
        self.registration.has_paid = True
        self.registration.save()

    @property
    def is_successful(self):
        return self.payment_status == 'completed'

    # Add properties to make it compatible with your PesaPalService
    @property
    def full_name(self):
        """For PesaPalService compatibility"""
        return self.registration.full_name

    @property  
    def phone(self):
        """For PesaPalService compatibility"""
        return self.customer_phone

    @property
    def email(self):
        """For PesaPalService compatibility"""
        return self.customer_email