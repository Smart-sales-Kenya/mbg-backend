from django.shortcuts import render

# Create your views here.
from django.conf import settings
from django.core.mail import send_mail
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import ContactMessage, TeamMember, GalleryItem, GalleryCategory
from .serializers import ContactMessageSerializer,TeamMemberSerializer,GalleryItemSerializer,GalleryCategorySerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import Testimonial
from .serializers import TestimonialSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hello_world(request):
    user = request.user
    return Response({"message": f"Hello, {user.username}!"})

@ensure_csrf_cookie
def get_csrf_token(request):
    return JsonResponse({"message": "CSRF cookie set"})


@api_view(['POST'])
def contact_view(request):
    serializer = ContactMessageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Your message has been received successfully!'}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
def team_list(request):
    members = TeamMember.objects.all().order_by('category')
    serializer = TeamMemberSerializer(members, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
def gallery_list(request):
    category_slug = request.GET.get('category')
    if category_slug:
        items = GalleryItem.objects.filter(category__slug=category_slug)
    else:
        items = GalleryItem.objects.all()
    
    serializer = GalleryItemSerializer(items, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
def category_list(request):
    categories = GalleryCategory.objects.all()
    
    serializer = GalleryCategorySerializer(categories, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
def get_testimonials(request):
    """
    Fetch all testimonials
    """
    testimonials = Testimonial.objects.all()
    serializer = TestimonialSerializer(testimonials, many=True, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Event, EventRegistration
from .serializers import EventSerializer, EventRegistrationSerializer

# -----------------------------
# Events
# -----------------------------
@api_view(['GET'])
def event_list(request):
    """
    GET: List all upcoming events
    """
    events = Event.objects.all().order_by('start_date')
    serializer = EventSerializer(events, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def event_detail(request, pk):
    """
    GET: Retrieve a single event by ID
    """
    try:
        event = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = EventSerializer(event)
    return Response(serializer.data)

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import Event, EventRegistration
from .serializers import EventRegistrationSerializer


# -----------------------------
# Event Registrations
# -----------------------------
@api_view(['GET', 'POST'])
def event_registration_list(request):
    """
    GET: List all registrations
    POST: Create a new registration and send emails
    """
    if request.method == 'GET':
        registrations = EventRegistration.objects.all()
        serializer = EventRegistrationSerializer(registrations, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = EventRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            registration = serializer.save()

            # Send emails (user + admins)
            send_registration_emails(registration)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
def event_registration_by_event(request, event_id):
    """
    GET: List all registrations for a specific event
    POST: Create registration for a specific event and send emails
    """
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        registrations = EventRegistration.objects.filter(event=event)
        serializer = EventRegistrationSerializer(registrations, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = EventRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            registration = serializer.save(event=event)

            # Send emails (user + admins)
            send_registration_emails(registration)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------
# Helper: Send Emails to User + Admins
# -----------------------------
def send_registration_emails(registration):
    """
    Sends:
    1️⃣ Confirmation email to the user
    2️⃣ Notification email to both admins
    """
    event = registration.event
    user_email = registration.email
    user_name = registration.full_name

    # Shared context
    context = {
        'name': user_name,
        'email': user_email,
        'event': event.title,
        'date': event.start_date,
        'location': event.location,
    }

    # ---- USER EMAIL ----
    user_subject = f"🎉 You're Registered for {event.title}!"
    user_html_content = render_to_string('emails/event_registration_user.html', context)
    user_text_content = render_to_string('emails/event_registration_user.txt', context)

    user_msg = EmailMultiAlternatives(
        subject=user_subject,
        body=user_text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user_email],
    )
    user_msg.attach_alternative(user_html_content, "text/html")
    user_msg.send(fail_silently=False)

    # ---- ADMIN EMAIL ----
    admin_subject = f"📩 New Registration: {user_name} for {event.title}"
    admin_html_content = render_to_string('emails/event_registration_admin.html', context)
    admin_text_content = render_to_string('emails/event_registration_admin.txt', context)

    admin_emails = settings.ADMIN_EMAILS
    admin_msg = EmailMultiAlternatives(
        subject=admin_subject,
        body=admin_text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=admin_emails,
    )
    admin_msg.attach_alternative(admin_html_content, "text/html")
    admin_msg.send(fail_silently=False)
