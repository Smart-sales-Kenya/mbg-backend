from django.shortcuts import render
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.shortcuts import get_object_or_404
import logging
import os
from google.oauth2 import id_token
from google.auth.transport import requests

# Import models and serializers
from .models import (
    ContactMessage, TeamMember, GalleryItem, GalleryCategory, 
    Testimonial, Event, EventRegistration, Program, ProgramRegistration, Payment
)
from .serializers import (
    ContactMessageSerializer, TeamMemberSerializer, GalleryItemSerializer,
    GalleryCategorySerializer, TestimonialSerializer, EventSerializer,
    EventRegistrationSerializer, ProgramSerializer, ProgramRegistrationSerializer,
    PaymentSerializer, MyTokenObtainPairSerializer
)
from .services.pesapal_service import PesaPalService
from rest_framework_simplejwt.views import TokenObtainPairView
from django.http import HttpResponse
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

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
    testimonials = Testimonial.objects.all()
    serializer = TestimonialSerializer(testimonials, many=True, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)

# Events
@api_view(['GET'])
def event_list(request):
    events = Event.objects.all().order_by('start_date')
    serializer = EventSerializer(events, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def event_detail(request, pk):
    try:
        event = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = EventSerializer(event)
    return Response(serializer.data)

@api_view(['GET', 'POST'])
def event_registration_list(request):
    if request.method == 'GET':
        registrations = EventRegistration.objects.all()
        serializer = EventRegistrationSerializer(registrations, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = EventRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            registration = serializer.save()
            send_registration_emails(registration)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def event_registration_by_event(request, event_id):
    """
    GET: List all registrations for a specific event
    POST: Create registration for a specific event and send emails with payment links
    """
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        logger.error(f"Event not found with ID: {event_id}")
        return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        registrations = EventRegistration.objects.filter(event=event)
        serializer = EventRegistrationSerializer(registrations, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = EventRegistrationSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.error(f"Registration validation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            registration = serializer.save(event=event)

            # Create payment record for paid events
            payment = None
            if not event.is_free:
                try:
                    payment = Payment.objects.create(
                        registration=registration,
                        amount=event.investment_amount,
                        currency=event.currency,
                        payment_method='pesapal',
                        customer_email=registration.email,
                        customer_phone=registration.phone,
                        description=f"Event Registration: {event.title}"
                    )
                    
                    registration.registration_status = 'pending'
                    registration.save()
                    
                except Exception as payment_error:
                    logger.error(f"Failed to create payment record: {str(payment_error)}")
            else:
                registration.registration_status = 'confirmed'
                registration.save()

            # Send emails
            try:
                send_registration_emails(registration)
            except Exception as email_error:
                logger.error(f"Failed to send emails: {str(email_error)}")

            # Prepare response data
            response_data = serializer.data
            
            if not event.is_free and payment:
                response_data['payment_required'] = True
                response_data['payment_id'] = str(payment.id)
                response_data['payment_amount'] = str(payment.amount)
                response_data['payment_currency'] = payment.currency
                response_data['payment_url'] = f"/api/payments/initiate/{registration.id}/"
                response_data['registration_status'] = 'pending'
            else:
                response_data['payment_required'] = False
                response_data['registration_status'] = 'confirmed'

            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as save_error:
            logger.error(f"Error saving registration: {str(save_error)}")
            return Response(
                {'error': 'Failed to save registration', 'details': str(save_error)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
def send_registration_emails(registration):
    event = registration.event
    user_email = registration.email
    user_name = registration.full_name

    # Generate payment URL for paid events
    payment_url = None
    if not event.is_free:
        payment_url = f"{settings.FRONTEND_URL}/payment/{registration.id}/"

    context = {
        'name': user_name,
        'email': user_email,
        'event': event.title,
        'date': event.start_date,
        'location': event.location,
        'is_free_event': event.is_free,
        'payment_url': payment_url,
        'amount': event.investment_amount if not event.is_free else 0,
        'currency': event.currency,
    }

    # USER EMAIL
    subject = (
        f"🎉 You're Registered for {event.title}!"
        if event.is_free
        else f"🎉 You're Registered for {event.title} - Complete Your Payment"
    )

    user_msg = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string('emails/event_registration_user.txt', context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user_email],
    )
    user_msg.attach_alternative(
        render_to_string('emails/event_registration_user.html', context), "text/html"
    )
    user_msg.send()

    # ADMIN EMAIL
    admin_msg = EmailMultiAlternatives(
        subject=f"📩 New Registration: {user_name} for {event.title}",
        body=render_to_string('emails/event_registration_admin.txt', context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=settings.ADMIN_EMAILS,
    )
    admin_msg.attach_alternative(
        render_to_string('emails/event_registration_admin.html', context), "text/html"
    )
    admin_msg.send()

# Programs
@api_view(['GET'])
def program_list_endpoint(request):
    programs = Program.objects.all()
    serializer = ProgramSerializer(programs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
from .models import ProgramPayment
# views.py
@api_view(['POST'])
def program_register_endpoint(request, program_id):
    """Handle program registration"""
    try:
        # Get the program
        try:
            program = Program.objects.get(id=program_id)
        except Program.DoesNotExist:
            return Response(
                {'error': 'Program not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Create registration
        serializer = ProgramRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            registration = serializer.save(program=program)
            
            # Create program payment record
            payment = ProgramPayment.objects.create(
                registration=registration,
                customer_email=registration.email,
                customer_phone=registration.phone_number,
                description=f"Program: {program.title}"
            )
            
            return Response({
                'id': str(registration.id),
                'message': 'Registration successful',
                'payment_id': str(payment.id)
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Program registration error: {str(e)}")
        return Response(
            {'error': f'Registration failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
def send_program_registration_emails(registration):
    context = {
        'full_name': registration.full_name,
        'program': registration.program,
        'email': registration.email,
        'phone_number': registration.phone_number,
        'company_name': registration.company_name,
        'role': registration.role,
        'team_size': registration.team_size,
        'challenges': registration.challenges,
    }

    # User Email
    user_subject = f"🎉 You're Registered for {registration.program.title}!"
    html_user = render_to_string('emails/program_registration_user.html', context)
    text_user = render_to_string('emails/program_registration_user.txt', context)

    user_msg = EmailMultiAlternatives(
        subject=user_subject,
        body=text_user,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[registration.email],
    )
    user_msg.attach_alternative(html_user, "text/html")
    user_msg.send(fail_silently=False)

    # Admin Email
    admin_subject = f"📩 New Program Registration: {registration.full_name}"
    html_admin = render_to_string('emails/program_registration_admin.html', context)
    text_admin = render_to_string('emails/program_registration_admin.txt', context)

    admin_emails = settings.ADMIN_EMAILS
    admin_msg = EmailMultiAlternatives(
        subject=admin_subject,
        body=text_admin,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=admin_emails,
    )
    admin_msg.attach_alternative(html_admin, "text/html")
    admin_msg.send(fail_silently=False)

# Google Auth
# @csrf_exempt
def sign_in(request):
    return render(request, 'sign_in.html')

# @csrf_exempt
def auth_receiver(request):
    token = request.POST['credential']
    try:
        user_data = id_token.verify_oauth2_token(
            token, requests.Request(), os.environ['GOOGLE_OAUTH_CLIENT_ID']
        )
    except ValueError:
        return HttpResponse(status=403)
    
    request.session['user_data'] = user_data
    return redirect('sign_in')

def sign_out(request):
    del request.session['user_data']
    return redirect('sign_in')

# Payment Views
@api_view(['POST'])
def initiate_payment(request, registration_id):
    """Initiate PesaPal payment for a registration"""
    try:
        registration = EventRegistration.objects.get(id=registration_id)
        
        if not hasattr(registration, 'payment'):
            return Response(
                {'error': 'Payment record not found. Please contact support.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        payment = registration.payment
        
        if registration.event.is_free:
            return Response(
                {'error': 'This is a free event, no payment required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pesapal = PesaPalService()
        order_response = pesapal.submit_order(payment)
        
        if order_response and order_response.get('redirect_url'):
            return Response({
                'message': 'Payment initiated successfully',
                'payment_url': order_response.get('redirect_url'),
                'order_tracking_id': payment.pesapal_order_tracking_id,
                'payment_id': str(payment.id)
            })
        else:
            return Response(
                {'error': 'Failed to initiate payment with PesaPal. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except EventRegistration.DoesNotExist:
        return Response(
            {'error': 'Registration not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Payment initiation error: {str(e)}")
        return Response(
            {'error': f'Payment initiation failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def payment_status(request, payment_id):
    """Check payment status"""
    try:
        payment = get_object_or_404(Payment, id=payment_id)
        
        if payment.pesapal_order_tracking_id:
            pesapal = PesaPalService()
            status_response = pesapal.get_transaction_status(payment.pesapal_order_tracking_id)
            
            if status_response:
                return Response({
                    'payment_status': payment.payment_status,
                    'pesapal_status': status_response,
                    'payment_details': PaymentSerializer(payment).data
                })
        
        return Response({
            'payment_status': payment.payment_status,
            'payment_details': PaymentSerializer(payment).data
        })
        
    except Exception as e:
        logger.error(f"Payment status error: {str(e)}")
        return Response(
            {'error': f'Failed to get payment status: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
from django.http import HttpResponseRedirect
@api_view(['GET', 'POST'])
def pesapal_callback(request):
    """Handle PesaPal callback after payment - supports both GET and POST"""
    try:
        # Extract parameters
        if request.method == 'GET':
            order_tracking_id = request.GET.get('OrderTrackingId')
            order_merchant_reference = request.GET.get('OrderMerchantReference')
        else:
            order_tracking_id = request.GET.get('OrderTrackingId') or request.data.get('OrderTrackingId')
            order_merchant_reference = request.GET.get('OrderMerchantReference') or request.data.get('OrderMerchantReference')
        
        logger.info(f"🔔 PesaPal Callback Received")
        logger.info(f"OrderTrackingId: {order_tracking_id}")
        logger.info(f"OrderMerchantReference: {order_merchant_reference}")
        
        if not order_tracking_id:
            # If no tracking ID, redirect to frontend with error
            frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8080')
            frontend_url = f"{frontend_base_url}/payment-result?status=error&message=Missing order tracking ID"
            logger.error(f"❌ Missing order tracking ID")
            return HttpResponseRedirect(frontend_url)
        
        # Get payment record
        try:
            payment = Payment.objects.get(pesapal_order_tracking_id=order_tracking_id)
            logger.info(f"✅ Payment found: {payment.id}")
            logger.info(f"Current payment status: {payment.payment_status}")
            logger.info(f"Current registration status: {payment.registration.registration_status}")
            
        except Payment.DoesNotExist:
            logger.error(f"❌ No payment found for tracking ID: {order_tracking_id}")
            frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8080')
            frontend_url = f"{frontend_base_url}/payment-result?status=error&message=Payment not found"
            return HttpResponseRedirect(frontend_url)
        
        # Initialize PesaPal service and get transaction status
        pesapal = PesaPalService()
        logger.info(f"🔄 Checking transaction status with PesaPal...")
        status_response = pesapal.get_transaction_status(order_tracking_id)
        
        logger.info(f"📡 PesaPal status response: {status_response}")
        
        payment_updated = False
        payment_status = payment.payment_status
        registration_status = payment.registration.registration_status
        
        if status_response:
            status_code = status_response.get('status_code')
            payment_method = status_response.get('payment_method')
            transaction_id = status_response.get('transaction_id')
            payment_status_description = status_response.get('payment_status_description')
            
            logger.info(f"🔍 Status Details:")
            logger.info(f"  - Status Code: {status_code} (type: {type(status_code)})")
            logger.info(f"  - Payment Method: {payment_method}")
            logger.info(f"  - Transaction ID: {transaction_id}")
            logger.info(f"  - Status Description: {payment_status_description}")
            
            # ✅ FIXED: Compare with both string and integer values
            if status_code in [1, '1']:  # ✅ COMPLETED (handles both string and integer)
                payment.payment_status = 'completed'
                payment.payment_completed_at = timezone.now()
                payment.payment_method = payment_method or 'pesapal'
                payment.pesapal_transaction_id = transaction_id
                
                # Update registration status
                payment.registration.registration_status = 'confirmed'
                payment.registration.save()
                
                payment_status = 'completed'
                registration_status = 'confirmed'
                payment_updated = True
                
                logger.info(f"✅ PAYMENT COMPLETED! Registration confirmed for {payment.registration.email}")
                
                # Send payment confirmation email
                try:
                    send_payment_confirmation_email(payment)
                    logger.info("✅ Payment confirmation email sent successfully")
                except Exception as email_error:
                    logger.error(f"❌ Failed to send payment confirmation email: {str(email_error)}")
                
            elif status_code in [2, '2']:  # Failed
                payment.payment_status = 'failed'
                payment_status = 'failed'
                payment_updated = True
                logger.warning(f"❌ Payment failed for {payment.registration.email}")
            
            elif status_code in [0, '0']:  # Pending
                payment.payment_status = 'pending'
                payment_status = 'pending'
                payment_updated = True
                logger.info(f"⏳ Payment still pending for {payment.registration.email}")
            
            else:
                logger.warning(f"⚠️ Unknown payment status code: {status_code} (type: {type(status_code)})")
                # Keep current status if unknown
            
            if payment_updated:
                payment.save()
        
        # ✅ FIXED: PROPERLY construct frontend URL using settings
        frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8080')
        
        # Ensure the base URL doesn't have a trailing slash
        frontend_base_url = frontend_base_url.rstrip('/')
        
        # Build the complete redirect URL
        frontend_url = f"{frontend_base_url}/payment-result?status={payment_status}&order_tracking_id={order_tracking_id}"
        
        if payment_status == 'completed':
            frontend_url += "&message=Payment completed successfully"
        elif payment_status == 'failed':
            frontend_url += "&message=Payment failed. Please try again."
        elif payment_status == 'pending':
            frontend_url += "&message=Payment is still processing"
        
        logger.info(f"🔀 Redirecting to frontend: {frontend_url}")
        
        # Redirect to frontend
        return HttpResponseRedirect(frontend_url)
        
    except Exception as e:
        logger.error(f"❌ PesaPal callback processing failed: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # ✅ FIXED: Proper error redirect URL
        frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8080')
        frontend_base_url = frontend_base_url.rstrip('/')
        frontend_url = f"{frontend_base_url}/payment-result?status=error&message=Callback processing failed"
        return HttpResponseRedirect(frontend_url)
    
@api_view(['POST'])
def pesapal_ipn(request):
    """Handle PesaPal Instant Payment Notification (IPN)"""
    try:
        ipn_data = request.data
        order_tracking_id = ipn_data.get('OrderTrackingId')
        
        if not order_tracking_id:
            return Response({'error': 'Missing order tracking ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        payment = get_object_or_404(Payment, pesapal_order_tracking_id=order_tracking_id)
        pesapal = PesaPalService()
        
        validation_response = pesapal.validate_ipn(order_tracking_id)
        
        if validation_response and validation_response.get('status_code') == '1':
            payment.payment_status = 'completed'
            payment.payment_completed_at = timezone.now()
            payment.pesapal_transaction_id = validation_response.get('transaction_id')
            
            payment.registration.registration_status = 'confirmed'
            payment.registration.save()
            
            payment.save()
            
            # Send payment confirmation email
            send_payment_confirmation_email(payment)
            
        return Response({'message': 'IPN processed successfully'})
        
    except Exception as e:
        logger.error(f"PesaPal IPN error: {str(e)}")
        return Response(
            {'error': f'IPN processing failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def send_payment_confirmation_email(payment):
    """Send payment confirmation email to user"""
    registration = payment.registration
    event = registration.event
    
    context = {
        'name': registration.full_name,
        'event': event.title,
        'date': event.start_date,
        'location': event.location,
        'amount': payment.amount,
        'currency': payment.currency,
        'transaction_id': payment.pesapal_transaction_id,
    }

    subject = f"✅ Payment Confirmed for {event.title}"
    html_content = render_to_string('emails/payment_confirmation.html', context)
    text_content = render_to_string('emails/payment_confirmation.txt', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[registration.email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)
    

# views.py
@api_view(['POST'])
def initiate_program_payment(request, registration_id):
    """Initiate payment for program registration"""
    try:
        registration = get_object_or_404(ProgramRegistration, id=registration_id)
        
        # Get or create payment
        payment, created = ProgramPayment.objects.get_or_create(
            registration=registration,
            defaults={
                'customer_email': registration.email,
                'customer_phone': registration.phone_number,
                'description': f"Program: {registration.program.title}"
            }
        )

        # Initiate payment
        payment_service = ProgramPaymentService()
        payment_data = payment_service.initiate_payment(payment)

        return Response({
            'payment_url': payment_data['payment_url'],
            'order_tracking_id': payment_data['order_tracking_id'],
            'message': 'Payment initiated successfully'
        })

    except Exception as e:
        logger.error(f"Program payment initiation error: {str(e)}")
        return Response(
            {'error': f'Payment initiation failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def program_payment_status(request, payment_id):
    """Check program payment status"""
    try:
        payment = get_object_or_404(ProgramPayment, id=payment_id)
        
        if payment.pesapal_order_tracking_id:
            payment_service = ProgramPaymentService()
            status_response = payment_service.get_transaction_status(payment.pesapal_order_tracking_id)
            
            if status_response:
                return Response({
                    'payment_status': payment.payment_status,
                    'pesapal_status': status_response,
                    'payment_details': ProgramPaymentSerializer(payment).data
                })
        
        return Response({
            'payment_status': payment.payment_status,
            'payment_details': ProgramPaymentSerializer(payment).data
        })
        
    except Exception as e:
        logger.error(f"Program payment status error: {str(e)}")
        return Response(
            {'error': f'Failed to get payment status: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )