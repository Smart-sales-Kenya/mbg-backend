from django.db import models


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
    image = models.ImageField(upload_to='team_images/')
    bio = models.TextField()
    email = models.EmailField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)

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
    image = models.ImageField(upload_to='gallery_images/', blank=True, null=True)
    video_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return  f"{self.category.name} Item"


class Testimonial(models.Model):
    author = models.CharField(max_length=100)
    company = models.CharField(max_length=150)
    text = models.TextField(max_length=250)
    logo = models.ImageField(upload_to='testimonials/logos/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author} - {self.company}"



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

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=255)
    participants_limit = models.PositiveIntegerField()
    duration = models.CharField(max_length=100, blank=True)  # e.g. "16-Week Program", "1-Day Workshop"
    description = models.TextField()
    
    # Payment info
    investment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='KES')  # Default to Kenyan Shillings
    is_free = models.BooleanField(default=False)

    status = models.CharField(max_length=50, choices=EVENT_STATUS_CHOICES)
    registration_open = models.BooleanField(default=True)
    image = models.ImageField(upload_to='events/', blank=True, null=True)

    def __str__(self):
        return self.title


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

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('free', 'Free'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    company = models.CharField(max_length=100)
    job_title = models.CharField(max_length=100)
    industry = models.CharField(max_length=100, blank=True)
    experience_level = models.CharField(max_length=50, choices=EXPERIENCE_CHOICES, blank=True)
    goals = models.TextField(blank=True)
    heard_about = models.CharField(max_length=50, choices=HEARD_ABOUT_CHOICES, blank=True)

    # Payment info
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    # payment_method = models.CharField(max_length=50, blank=True)  # e.g., M-Pesa, Card

    registration_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.event.title}"
