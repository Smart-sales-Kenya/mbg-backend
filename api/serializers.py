from rest_framework import serializers
from .models import ContactMessage,TeamMember,Testimonial
from rest_framework import serializers

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# api/serializers.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import logging
logger = logging.getLogger(__name__)

# In your EventRegistrationSerializer class, add this:
class EventRegistrationSerializer(serializers.ModelSerializer):
    # ... your existing fields ...
    
    def validate(self, data):
        """
        Add validation debugging
        """
        logger.info("=== SERIALIZER VALIDATION START ===")
        logger.info(f"Data being validated: {data}")
        
        # Check required fields
        required_fields = ['full_name', 'email', 'phone', 'company', 'job_title']
        for field in required_fields:
            value = data.get(field)
            logger.info(f"Required field '{field}': '{value}' (exists: {field in data}, truthy: {bool(value)})")
        
        # Check event field specifically
        event_value = data.get('event')
        logger.info(f"Event field in validation: '{event_value}' (type: {type(event_value)})")
        
        logger.info("=== SERIALIZER VALIDATION END ===")
        return data
    
    def create(self, validated_data):
        """
        Add creation debugging
        """
        logger.info("=== SERIALIZER CREATE START ===")
        logger.info(f"Validated data for creation: {validated_data}")
        
        # The event should come from the context, not from validated_data
        event = self.context.get('event')
        logger.info(f"Event from context: {event}")
        
        # Remove event from validated_data if it exists (it shouldn't)
        if 'event' in validated_data:
            logger.warning(f"Event found in validated_data: {validated_data['event']}")
            del validated_data['event']
        
        logger.info(f"Final validated data without event: {validated_data}")
        
        try:
            instance = EventRegistration.objects.create(event=event, **validated_data)
            logger.info(f"Registration instance created: {instance}")
            logger.info("=== SERIALIZER CREATE COMPLETED ===")
            return instance
        except Exception as e:
            logger.error(f"Error in serializer create: {str(e)}")
            raise
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'  # use email for login

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # add custom claims if needed
        token['email'] = user.email
        return token


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = '__all__'
        read_only_fields = ['created_at']
        


class TeamMemberSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = TeamMember
        fields = '__all__'

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image:
            return request.build_absolute_uri(obj.image.url)
        return None


from rest_framework import serializers
from .models import GalleryCategory, GalleryItem

class GalleryCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GalleryCategory
        fields = ['id', 'name', 'slug']


class GalleryItemSerializer(serializers.ModelSerializer):
    # return full absolute URL for image
    image = serializers.SerializerMethodField()
    category = GalleryCategorySerializer(read_only=True)

    class Meta:
        model = GalleryItem
        fields = ['id', 'category',  'image', 'video_url', 'created_at']

    def get_image(self, obj):
        request = self.context.get('request', None)
        if obj.image:
            try:
                # if serializer has request in context, build absolute uri
                if request:
                    return request.build_absolute_uri(obj.image.url)
                # fallback to returning the relative URL
                return obj.image.url
            except Exception:
                return None
        return None

class TestimonialSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(use_url=True)

    class Meta:
        model = Testimonial
        fields = ['id', 'author', 'company', 'text', 'logo', 'created_at']
        
        
from rest_framework import serializers
from .models import Event

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'subtitle',
            'tagline',
            'category',
            'start_date',
            'end_date',
            'start_time',
            'end_time',
            'location',
            'participants_limit',
            'duration',
            'description',
            'investment_amount',
            'currency',
            'is_free',
            'status',
            'registration_open',
            'image',
        ]

from rest_framework import serializers
from .models import EventRegistration, Event, Payment
class EventRegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.ReadOnlyField(source='event.title')
    is_free_event = serializers.ReadOnlyField(source='event.is_free')
    payment_status = serializers.SerializerMethodField()
    payment_amount = serializers.SerializerMethodField()

    class Meta:
        model = EventRegistration
        fields = [
            'id',
            'event',              # event ID
            'event_title',        # read-only title
            'is_free_event',      # read-only free flag
            'full_name',
            'email',
            'phone',
            'company',
            'job_title',
            'industry',
            'experience_level',
            'goals',
            'heard_about',
            'registration_status',
            'registration_date',
            'payment_status',     # from related Payment model
            'payment_amount',     # from related Payment model
        ]
        read_only_fields = [
            'id', 'registration_date', 'event_title', 'is_free_event', 
            'registration_status', 'payment_status', 'payment_amount'
        ]

    def get_payment_status(self, obj):
        """Get payment status from related Payment model"""
        if hasattr(obj, 'payment') and obj.payment:
            return obj.payment.payment_status
        elif obj.event.is_free:
            return 'free'
        return 'pending'

    def get_payment_amount(self, obj):
        """Get payment amount from related Payment model"""
        if hasattr(obj, 'payment') and obj.payment:
            return obj.payment.amount
        elif obj.event.is_free:
            return 0
        return obj.event.investment_amount

    def create(self, validated_data):
        """
        Create EventRegistration and related Payment if needed
        """
        # Remove any payment fields that might accidentally be in validated_data
        validated_data.pop('payment_status', None)
        validated_data.pop('payment_amount', None)
        
        # Create the registration
        registration = EventRegistration.objects.create(**validated_data)
        
        # Create Payment record for paid events
        if not registration.event.is_free:
            Payment.objects.create(
                registration=registration,
                amount=registration.event.investment_amount,
                currency=registration.event.currency,
                customer_email=registration.email,
                customer_phone=registration.phone,
                description=f"Event registration: {registration.event.title}",
                payment_method='pesapal',  # Default to PesaPal
                payment_status='pending'
            )
        else:
            # For free events, you might still want to create a payment record with status 'free'
            Payment.objects.create(
                registration=registration,
                amount=0,
                currency=registration.event.currency,
                customer_email=registration.email,
                customer_phone=registration.phone,
                description=f"Free event registration: {registration.event.title}",
                payment_method='free',
                payment_status='free'
            )
        
        return registration

from rest_framework import serializers
from .models import ProgramCategory, Program, ProgramFeature, ProgramRegistration

# Category Serializer
class ProgramCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramCategory
        fields = ['id', 'name', 'slug']


# Feature Serializer
class ProgramFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramFeature
        fields = ['id', 'description']


# Program Serializer
class ProgramSerializer(serializers.ModelSerializer):
    category = ProgramCategorySerializer(read_only=True)
    features = ProgramFeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Program
        fields = [
            'id', 'title', 'category', 'duration', 'price', 'description',
            'focus', 'outcome', 'skills', 'format', 'badge',  'features'
        ]


# Program Registration Serializer
class ProgramRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramRegistration
        fields = [
            'id', 'program', 'full_name', 'email', 'phone_number',
            'company_name', 'role', 'team_size', 'challenges',
            'has_paid', 'payment_reference', 'registered_at'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    registration_details = serializers.SerializerMethodField()
    event_title = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id',
            'amount',
            'currency',
            'payment_method',
            'payment_status',
            'registration_details',
            'event_title',
            'pesapal_order_tracking_id',
            'pesapal_payment_url',
            'payment_initiated_at',
            'payment_completed_at',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_registration_details(self, obj):
        return {
            'full_name': obj.registration.full_name,
            'email': obj.registration.email,
            'phone': obj.registration.phone
        }

    def get_event_title(self, obj):
        return obj.registration.event.title