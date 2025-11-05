from rest_framework import serializers
from .models import ContactMessage,TeamMember,Testimonial
from rest_framework import serializers

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# api/serializers.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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
            'id', 'title', 'category', 'start_date', 'end_date', 
            'start_time', 'end_time', 'location', 'participants_limit', 
            'duration', 'description', 'investment_amount', 'currency', 
            'is_free', 'status', 'registration_open', 'image'
        ]

from rest_framework import serializers
from .models import EventRegistration, Event

class EventRegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.ReadOnlyField(source='event.title')
    is_free_event = serializers.ReadOnlyField(source='event.is_free')

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
            'payment_status',
            'payment_amount',
            'registration_date',
        ]
        read_only_fields = ['payment_status', 'payment_amount', 'registration_date', 'event_title', 'is_free_event']

    def create(self, validated_data):
        """
        Automatically set payment_status and amount for free events
        """
        event = validated_data.get('event')
        if event.is_free:
            validated_data['payment_status'] = 'free'
            validated_data['payment_amount'] = 0
        else:
            validated_data['payment_status'] = 'pending'
            validated_data['payment_amount'] = event.investment_amount
        return super().create(validated_data)

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
            'focus', 'outcome', 'skills', 'format', 'badge', 'icon_name', 'features'
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
