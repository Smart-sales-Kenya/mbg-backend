from django.contrib import admin
from .models import ContactMessage
from .models import TeamMember,GalleryCategory, GalleryItem


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


@admin.register(GalleryCategory)
class GalleryCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ('name', 'slug')

@admin.register(GalleryItem)
class GalleryItemAdmin(admin.ModelAdmin):
    list_display = ( 'category', 'created_at')
    list_filter = ('category',)
    
    
from django.contrib import admin
from .models import Testimonial

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('author', 'company', 'created_at')
    search_fields = ('author', 'company')
    ordering = ('-created_at',)



from django.contrib import admin
from .models import Event, EventRegistration

# -----------------------------
# EventRegistration Inline
# -----------------------------
class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    readonly_fields = ('payment_status', 'payment_amount', 'registration_date')
    fields = ('full_name', 'email', 'phone', 'company', 'job_title', 'experience_level', 
              'payment_status', 'payment_amount', 'registration_date')
    show_change_link = True

# -----------------------------
# Event Admin
# -----------------------------
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'start_date', 'end_date', 'location', 'participants_limit', 'status', 'is_free')
    list_filter = ('category', 'status', 'is_free')
    search_fields = ('title', 'location', 'description')
    inlines = [EventRegistrationInline]
    

# -----------------------------
# EventRegistration Admin
# -----------------------------
@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'event', 'email', 'phone', 'payment_status', 'payment_amount', 'payment_date')
    list_filter = ('event', 'payment_status', 'experience_level')
    search_fields = ('full_name', 'email', 'company', 'job_title')
    readonly_fields = ('registration_date',)


from django.contrib import admin
from .models import ProgramCategory, Program, ProgramFeature,ProgramRegistration

class ProgramFeatureInline(admin.TabularInline):
    """
    Inline editing for program features inside a Program
    """
    model = ProgramFeature
    extra = 1  # Number of blank feature rows to display


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'duration', 'price', 'badge')
    list_filter = ('category', 'badge')
    search_fields = ('title', 'description', 'focus', 'outcome')
    inlines = [ProgramFeatureInline]
    prepopulated_fields = {"slug": ("title",)} if hasattr(Program, 'slug') else {}

    
@admin.register(ProgramCategory)
class ProgramCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProgramFeature)
class ProgramFeatureAdmin(admin.ModelAdmin):
    list_display = ('program', 'description')
    search_fields = ('description',)

@admin.register(ProgramRegistration)
class ProgramRegistrationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "program", "team_size", "has_paid", "registered_at")
    list_filter = ("program", "team_size", "has_paid")
    search_fields = ("full_name", "email", "company_name", "role", "challenges")