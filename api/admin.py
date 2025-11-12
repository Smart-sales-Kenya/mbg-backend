from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ContactMessage, TeamMember, GalleryCategory, GalleryItem, 
    Testimonial, Event, EventRegistration, Payment,
    ProgramCategory, Program, ProgramFeature, ProgramRegistration
)


# ==================== CONTACT & TEAM ADMIN ====================
@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'phone', 'created_at')
    list_filter = ('subject', 'created_at')
    search_fields = ('name', 'email', 'message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'category', 'email')
    list_filter = ('category',)
    search_fields = ('name', 'role')


# ==================== GALLERY ADMIN ====================
@admin.register(GalleryCategory)
class GalleryCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ('name', 'slug')


@admin.register(GalleryItem)
class GalleryItemAdmin(admin.ModelAdmin):
    list_display = ('category', 'created_at')
    list_filter = ('category',)
    list_per_page = 20


# ==================== TESTIMONIAL ADMIN ====================
@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('author', 'company', 'created_at')
    search_fields = ('author', 'company')
    ordering = ('-created_at',)


# ==================== EVENT & REGISTRATION ADMIN ====================
class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    readonly_fields = ('registration_status_display', 'registration_date')
    fields = ('full_name', 'email', 'registration_status_display', 'registration_date')
    show_change_link = True
    
    def registration_status_display(self, obj):
        status_colors = {
            'pending': 'orange',
            'confirmed': 'green', 
            'cancelled': 'red',
            'waiting_list': 'blue',
        }
        color = status_colors.get(obj.registration_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            obj.get_registration_status_display().upper()
        )
    registration_status_display.short_description = "Status"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'start_date', 'location', 'status', 'is_free', 'available_spots_display')
    list_filter = ('category', 'status', 'is_free', 'registration_open')
    search_fields = ('title', 'location', 'description')
    readonly_fields = ('created_at', 'updated_at', 'available_spots_display')
    inlines = [EventRegistrationInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'subtitle', 'tagline', 'category', 'description')
        }),
        ('Date & Time', {
            'fields': ('start_date', 'end_date', 'start_time', 'end_time', 'duration')
        }),
        ('Location & Capacity', {
            'fields': ('location', 'participants_limit', 'available_spots_display')
        }),
        ('Pricing', {
            'fields': ('investment_amount', 'currency', 'is_free')
        }),
        ('Status', {
            'fields': ('status', 'registration_open')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def available_spots_display(self, obj):
        return obj.available_spots
    available_spots_display.short_description = 'Available Spots'


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'event_title', 'registration_status_badge', 'payment_status_display', 'registration_date')
    list_filter = ('registration_status', 'event', 'experience_level')
    search_fields = ('full_name', 'email', 'company', 'job_title', 'event__title')
    readonly_fields = ('registration_date', 'updated_at', 'payment_link_display')
    fieldsets = (
        ('Personal Information', {
            'fields': ('full_name', 'email', 'phone')
        }),
        ('Professional Information', {
            'fields': ('company', 'job_title', 'industry', 'experience_level')
        }),
        ('Event Information', {
            'fields': ('event', 'goals', 'heard_about')
        }),
        ('Registration Status', {
            'fields': ('registration_status', 'payment_link_display')
        }),
        ('Timestamps', {
            'fields': ('registration_date', 'updated_at')
        }),
    )
    
    def event_title(self, obj):
        return obj.event.title
    event_title.short_description = "Event"
    
    def registration_status_badge(self, obj):
        status_colors = {
            'pending': 'orange',
            'confirmed': 'green',
            'cancelled': 'red',
            'waiting_list': 'blue',
        }
        color = status_colors.get(obj.registration_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            obj.get_registration_status_display().upper()
        )
    registration_status_badge.short_description = "Status"
    
    def payment_status_display(self, obj):
        if hasattr(obj, 'payment'):
            status_colors = {
                'pending': 'orange',
                'initiated': 'blue',
                'completed': 'green',
                'failed': 'red',
                'cancelled': 'gray',
                'refunded': 'purple',
            }
            color = status_colors.get(obj.payment.payment_status, 'gray')
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
                color,
                obj.payment.get_payment_status_display().upper()
            )
        elif obj.event.is_free:
            return format_html(
                '<span style="background-color: green; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">FREE</span>'
            )
        return format_html(
            '<span style="background-color: gray; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">NO PAYMENT</span>'
        )
    payment_status_display.short_description = "Payment Status"
    
    def payment_link_display(self, obj):
        if hasattr(obj, 'payment'):
            url = f"/admin/api/payment/{obj.payment.id}/change/"
            return format_html('<a href="{}">View Payment Details</a>', url)
        elif not obj.event.is_free and obj.registration_status == 'pending':
            return "Payment not created yet"
        return "No payment required (Free event)"
    payment_link_display.short_description = "Payment Link"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('event', 'payment')


# ==================== PAYMENT ADMIN ====================
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('truncated_id', 'customer_email', 'amount_currency', 'payment_method', 'payment_status_badge', 'event_title', 'payment_initiated_at')
    list_filter = ('payment_status', 'payment_method', 'currency', 'payment_initiated_at')
    search_fields = ('customer_email', 'customer_phone', 'pesapal_order_tracking_id', 'registration__full_name', 'registration__event__title')
    readonly_fields = ('id', 'created_at', 'updated_at', 'registration_link', 'pesapal_order_tracking_id', 'pesapal_transaction_id')
    fieldsets = (
        ('Payment Information', {
            'fields': ('id', 'payment_status', 'amount', 'currency', 'payment_method')
        }),
        ('PesaPal Details', {
            'fields': ('pesapal_order_tracking_id', 'pesapal_transaction_id', 'pesapal_merchant_reference', 'pesapal_payment_url'),
            'classes': ('collapse',)
        }),
        ('Customer Information', {
            'fields': ('customer_email', 'customer_phone', 'description')
        }),
        ('Registration Link', {
            'fields': ('registration_link',)
        }),
        ('Timestamps', {
            'fields': ('payment_initiated_at', 'payment_completed_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def truncated_id(self, obj):
        return str(obj.id)[:8] + "..."
    truncated_id.short_description = "Payment ID"
    
    def amount_currency(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_currency.short_description = "Amount"
    
    def payment_status_badge(self, obj):
        status_colors = {
            'pending': 'orange',
            'initiated': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray',
            'refunded': 'purple',
        }
        color = status_colors.get(obj.payment_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            obj.get_payment_status_display().upper()
        )
    payment_status_badge.short_description = "Status"
    
    def event_title(self, obj):
        if obj.registration and obj.registration.event:
            return obj.registration.event.title
        return "No Event"
    event_title.short_description = "Event"
    
    def registration_link(self, obj):
        if obj.registration:
            url = f"/admin/api/eventregistration/{obj.registration.id}/change/"
            return format_html(
                '<a href="{}">{} - {}</a>',
                url,
                obj.registration.full_name,
                obj.registration.email
            )
        return "No Registration"
    registration_link.short_description = "Registration"


# ==================== PROGRAM ADMIN ====================
class ProgramFeatureInline(admin.TabularInline):
    model = ProgramFeature
    extra = 1


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'duration', 'price', 'badge')
    list_filter = ('category', 'badge')
    search_fields = ('title', 'description', 'focus', 'outcome')
    inlines = [ProgramFeatureInline]


@admin.register(ProgramCategory)
class ProgramCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProgramFeature)
class ProgramFeatureAdmin(admin.ModelAdmin):
    list_display = ('program', 'description')
    search_fields = ('description',)
    list_per_page = 20


@admin.register(ProgramRegistration)
class ProgramRegistrationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "program", "team_size", "has_paid", "registered_at")
    list_filter = ("program", "team_size", "has_paid")
    search_fields = ("full_name", "email", "company_name", "role", "challenges")
    readonly_fields = ('registered_at',)
    
    
from django.contrib import admin
from .models import ProgramPayment

@admin.register(ProgramPayment)
class ProgramPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'registration',
        'amount',
        'currency',
        'payment_method',
        'payment_status',
        'pesapal_order_tracking_id',
        'pesapal_transaction_id',
        'payment_initiated_at',
        'payment_completed_at',
        'created_at',
    )
    list_filter = (
        'payment_status',
        'payment_method',
        'currency',
        'created_at',
    )
    search_fields = (
        'id',
        'registration__full_name',
        'registration__email',
        'pesapal_order_tracking_id',
        'pesapal_transaction_id',
        'pesapal_merchant_reference',
        'customer_email',
        'customer_phone',
    )
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'payment_initiated_at',
        'payment_completed_at',
        'pesapal_order_tracking_id',
        'pesapal_transaction_id',
        'pesapal_merchant_reference',
        'pesapal_payment_url',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ("Payment Details", {
            "fields": (
                'registration',
                'amount',
                'currency',
                'payment_method',
                'payment_status',
                'description',
            ),
        }),
        ("Customer Information", {
            "fields": (
                'customer_email',
                'customer_phone',
            ),
        }),
        ("PesaPal Info", {
            "classes": ('collapse',),
            "fields": (
                'pesapal_order_tracking_id',
                'pesapal_transaction_id',
                'pesapal_merchant_reference',
                'pesapal_payment_url',
            ),
        }),
        ("Timestamps", {
            "classes": ('collapse',),
            "fields": (
                'payment_initiated_at',
                'payment_completed_at',
                'created_at',
                'updated_at',
            ),
        }),
    )

    def has_add_permission(self, request):
        """
        Prevent manual creation from admin — payments should be generated
        through the registration/payment workflow.
        """
        return False
