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
from .services.program_payment_service import ProgramPaymentService
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
# views.py - Your existing program registration endpoint

@api_view(['POST'])
def program_register_endpoint(request, program_id):
    """Register for a program and return registration ID for payment"""
    try:
        program = get_object_or_404(Program, id=program_id)
        serializer = ProgramRegistrationSerializer(data=request.data)
        
        if serializer.is_valid():
            # Save registration
            registration = serializer.save(program=program)
            
            # ✅ Send confirmation and admin emails
            try:
                send_program_registration_emails(registration)
            except Exception as email_error:
                logger.error(f"Email sending failed: {email_error}")

            # Return registration response
            return Response({
                'registration_id': registration.id,
                'program_title': program.title,
                'price': program.price,
                'message': 'Registration successful. Proceed to payment.',
                'payment_required': True,
                'next_step': f'/api/program-payments/initiate/{registration.id}/'
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
    """Handle PesaPal callback for BOTH event and program payments"""
    try:
        # Extract parameters
        if request.method == 'GET':
            order_tracking_id = request.GET.get('OrderTrackingId')
            order_merchant_reference = request.GET.get('OrderMerchantReference')
        else:
            order_tracking_id = request.GET.get('OrderTrackingId') or request.data.get('OrderTrackingId')
            order_merchant_reference = request.GET.get('OrderMerchantReference') or request.data.get('OrderMerchantReference')
        
        logger.info(f"🔔 UNIFIED PesaPal Callback Received - OrderTrackingId: {order_tracking_id}")
        
        if not order_tracking_id:
            frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8080')
            frontend_url = f"{frontend_base_url}/payment-result?status=error&message=Missing order tracking ID"
            return HttpResponseRedirect(frontend_url)
        
        # Try EVENT payment first
        try:
            payment = Payment.objects.get(pesapal_order_tracking_id=order_tracking_id)
            logger.info(f"✅ Processing as EVENT payment: {payment.id}")
            return handle_event_payment_callback(request, payment, order_tracking_id)
        except Payment.DoesNotExist:
            pass
        
        # Try PROGRAM payment
        try:
            payment = ProgramPayment.objects.get(pesapal_order_tracking_id=order_tracking_id)
            logger.info(f"✅ Processing as PROGRAM payment: {payment.id}")
            return handle_program_payment_callback(request, payment, order_tracking_id)
        except ProgramPayment.DoesNotExist:
            logger.error(f"❌ No payment found (event or program) for tracking ID: {order_tracking_id}")
            frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8080')
            frontend_url = f"{frontend_base_url}/payment-result?status=error&message=Payment not found"
            return HttpResponseRedirect(frontend_url)
        
    except Exception as e:
        logger.error(f"❌ Unified callback processing failed: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8080')
        frontend_base_url = frontend_base_url.rstrip('/')
        frontend_url = f"{frontend_base_url}/payment-result?status=error&message=Callback processing failed"
        return HttpResponseRedirect(frontend_url)

def handle_event_payment_callback(request, payment, order_tracking_id):
    """Handle event payment callback"""
    pesapal = PesaPalService()
    status_response = pesapal.get_transaction_status(order_tracking_id)
    
    logger.info(f"📡 Event payment status response: {status_response}")
    
    payment_updated = False
    payment_status = payment.payment_status
    
    if status_response:
        status_code = status_response.get('status_code')
        
        if status_code in [1, '1']:  # COMPLETED
            payment.payment_status = 'completed'
            payment.payment_completed_at = timezone.now()
            payment.payment_method = status_response.get('payment_method') or 'pesapal'
            payment.pesapal_transaction_id = status_response.get('transaction_id')
            
            # Update registration status
            payment.registration.registration_status = 'confirmed'
            payment.registration.save()
            
            payment_status = 'completed'
            payment_updated = True
            
            logger.info(f"✅ EVENT PAYMENT COMPLETED! Registration confirmed for {payment.registration.email}")
            
            # Send payment confirmation email
            try:
                send_program_payment_confirmation_email(payment)
                logger.info("✅ Event payment confirmation email sent successfully")
            except Exception as email_error:
                logger.error(f"❌ Failed to send event payment confirmation email: {str(email_error)}")
            
        elif status_code in [2, '2']:  # Failed
            payment.payment_status = 'failed'
            payment_status = 'failed'
            payment_updated = True
            
        elif status_code in [0, '0']:  # Pending
            payment.payment_status = 'pending'
            payment_status = 'pending'
            payment_updated = True
        
        if payment_updated:
            payment.save()
    
    # Redirect to frontend
    frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8080').rstrip('/')
    frontend_url = f"{frontend_base_url}/payment-result?status={payment_status}&order_tracking_id={order_tracking_id}&type=event"
    
    if payment_status == 'completed':
        frontend_url += "&message=Payment completed successfully"
    elif payment_status == 'failed':
        frontend_url += "&message=Payment failed. Please try again."
    elif payment_status == 'pending':
        frontend_url += "&message=Payment is still processing"
    
    logger.info(f"🔀 Redirecting event payment to: {frontend_url}")
    return HttpResponseRedirect(frontend_url)

def handle_program_payment_callback(request, payment, order_tracking_id):
    """Handle program payment callback"""
    program_payment_service = ProgramPaymentService()
    status_response = program_payment_service.get_transaction_status(order_tracking_id)
    
    logger.info(f"📡 Program payment status response: {status_response}")
    
    payment_updated = False
    payment_status = payment.payment_status
    
    if status_response:
        status_code = status_response.get('status_code')
        
        if status_code in [1, '1']:  # COMPLETED
            payment.payment_status = 'completed'
            payment.payment_completed_at = timezone.now()
            payment.payment_method = status_response.get('payment_method') or 'pesapal'
            payment.pesapal_transaction_id = status_response.get('transaction_id')
            
            # Update registration payment status
            payment.registration.has_paid = True
            payment.registration.save()
            
            payment_status = 'completed'
            payment_updated = True
            
            logger.info(f"✅ PROGRAM PAYMENT COMPLETED! Payment ID: {payment.id}")
            
            # Send program payment confirmation email
            try:
                send_program_payment_confirmation_email(payment)
                logger.info("✅ Program payment confirmation email sent successfully")
            except Exception as email_error:
                logger.error(f"❌ Failed to send program payment confirmation email: {str(email_error)}")
            
        elif status_code in [2, '2']:  # Failed
            payment.payment_status = 'failed'
            payment_status = 'failed'
            payment_updated = True
            
        elif status_code in [0, '0']:  # Pending
            payment.payment_status = 'pending'
            payment_status = 'pending'
            payment_updated = True
        
        if payment_updated:
            payment.save()
    
    # Redirect to frontend - use program-specific page
    frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8080').rstrip('/')
    frontend_url = f"{frontend_base_url}/program-payment-result?status={payment_status}&order_tracking_id={order_tracking_id}&payment_id={payment.id}"
    
    if payment_status == 'completed':
        frontend_url += "&message=Payment completed successfully"
    elif payment_status == 'failed':
        frontend_url += "&message=Payment failed. Please try again."
    elif payment_status == 'pending':
        frontend_url += "&message=Payment is still processing"
    
    logger.info(f"🔀 Redirecting program payment to: {frontend_url}")
    return HttpResponseRedirect(frontend_url)

@api_view(['POST'])
def pesapal_ipn(request):
    """
    Handle PesaPal Instant Payment Notification (IPN) for BOTH event and program payments
    """
    try:
        ipn_data = request.data
        order_tracking_id = ipn_data.get('OrderTrackingId')
        order_notification_type = ipn_data.get('OrderNotificationType')
        
        logger.info(f"🔄 PESAPAL IPN RECEIVED - OrderTrackingId: {order_tracking_id}, Type: {order_notification_type}")
        logger.info(f"📦 Full IPN Data: {ipn_data}")
        
        if not order_tracking_id:
            logger.error("❌ IPN missing OrderTrackingId")
            return Response({'error': 'Missing order tracking ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Try to find payment in EVENT payments first
        payment = None
        payment_type = None
        
        try:
            payment = Payment.objects.get(pesapal_order_tracking_id=order_tracking_id)
            payment_type = 'event'
            logger.info(f"✅ Found EVENT payment: {payment.id}")
        except Payment.DoesNotExist:
            logger.info(f"🔍 Event payment not found for tracking ID: {order_tracking_id}, checking program payments...")
        
        # If not found in events, try PROGRAM payments
        if not payment:
            try:
                payment = ProgramPayment.objects.get(pesapal_order_tracking_id=order_tracking_id)
                payment_type = 'program'
                logger.info(f"✅ Found PROGRAM payment: {payment.id}")
            except ProgramPayment.DoesNotExist:
                logger.error(f"❌ No payment found (event or program) for tracking ID: {order_tracking_id}")
                return Response(
                    {'error': 'Payment not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Validate the IPN with PesaPal
        pesapal = PesaPalService()
        validation_response = pesapal.validate_ipn(order_tracking_id)
        
        logger.info(f"📡 PesaPal validation response: {validation_response}")
        
        if validation_response:
            status_code = validation_response.get('status_code')
            payment_method = validation_response.get('payment_method')
            transaction_id = validation_response.get('transaction_id')
            
            logger.info(f"🔄 Processing payment status - Code: {status_code}, Type: {payment_type}")
            
            if status_code in [1, '1']:  # COMPLETED
                payment.payment_status = 'completed'
                payment.payment_completed_at = timezone.now()
                payment.payment_method = payment_method or 'pesapal'
                if transaction_id:
                    payment.pesapal_transaction_id = transaction_id
                
                payment.save()
                logger.info(f"✅ PAYMENT COMPLETED - {payment_type.upper()}: {payment.id}")
                
                # Handle completion based on payment type
                if payment_type == 'event':
                    # Confirm event registration
                    payment.registration.registration_status = 'confirmed'
                    payment.registration.save()
                    
                    # Send event payment confirmation email
                    try:
                        send_program_payment_confirmation_email(payment)
                        logger.info("✅ Event payment confirmation email sent successfully")
                    except Exception as email_error:
                        logger.error(f"❌ Failed to send event payment confirmation email: {str(email_error)}")
                        
                elif payment_type == 'program':
                    # Update program registration payment status
                    payment.registration.has_paid = True
                    payment.registration.payment_status = 'completed'  # Add this field if it exists
                    payment.registration.save()
                    
                    # Send program payment confirmation email
                    try:
                        send_program_payment_confirmation_email(payment)
                        logger.info("✅ Program payment confirmation email sent successfully")
                    except Exception as email_error:
                        logger.error(f"❌ Failed to send program payment confirmation email: {str(email_error)}")
                
                return Response({
                    'message': f'{payment_type.title()} payment completed successfully',
                    'payment_id': str(payment.id),
                    'order_tracking_id': order_tracking_id
                })
                
            elif status_code in [2, '2']:  # FAILED
                payment.payment_status = 'failed'
                payment.save()
                logger.warning(f"❌ PAYMENT FAILED - {payment_type.upper()}: {payment.id}")
                return Response({
                    'message': f'{payment_type.title()} payment failed',
                    'payment_id': str(payment.id),
                    'order_tracking_id': order_tracking_id
                })
                
            elif status_code in [0, '0']:  # PENDING
                payment.payment_status = 'pending'
                payment.save()
                logger.info(f"⏳ PAYMENT PENDING - {payment_type.upper()}: {payment.id}")
                return Response({
                    'message': f'{payment_type.title()} payment is pending',
                    'payment_id': str(payment.id),
                    'order_tracking_id': order_tracking_id
                })
            else:
                logger.warning(f"⚠️ UNKNOWN STATUS CODE: {status_code} for {payment_type} payment: {payment.id}")
                return Response({
                    'message': f'{payment_type.title()} payment has unknown status',
                    'status_code': status_code,
                    'payment_id': str(payment.id)
                })
        else:
            logger.error(f"❌ IPN validation failed for {order_tracking_id}")
            return Response(
                {'error': 'IPN validation failed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
    except Exception as e:
        logger.error(f"❌ PesaPal IPN processing error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response(
            {'error': f'IPN processing failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)

def send_program_payment_confirmation_email(payment):
    """Send payment confirmation email to the user and admins."""
    try:
        registration = payment.registration
        program = registration.program

        context = {
            'full_name': registration.full_name,
            'program_title': program.title,
            'duration': getattr(program, 'duration', 'N/A'),
            'amount': payment.amount,
            'currency': getattr(payment, 'currency', 'KES'),
            'transaction_id': payment.pesapal_transaction_id,
            'support_email': settings.DEFAULT_FROM_EMAIL,
        }

        # -------- USER EMAIL --------
        user_subject = f"✅ Payment Confirmed for {program.title}"
        user_text = render_to_string('emails/program_payment_confirmation.txt', context)
        user_html = render_to_string('emails/program_payment_confirmation.html', context)

        user_msg = EmailMultiAlternatives(
            subject=user_subject,
            body=user_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[registration.email],
        )
        user_msg.attach_alternative(user_html, "text/html")
        user_msg.send(fail_silently=False)

        logger.info(f"✅ Payment confirmation email sent to user: {registration.email}")

        # -------- ADMIN EMAIL --------
        if hasattr(settings, 'ADMIN_EMAILS') and settings.ADMIN_EMAILS:
            admin_subject = f"💰 New Program Payment: {registration.full_name} - {program.title}"
            admin_text = render_to_string('emails/program_payment_confirmation.txt', context)
            admin_html = render_to_string('emails/program_payment_confirmation.html', context)

            admin_msg = EmailMultiAlternatives(
                subject=admin_subject,
                body=admin_text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=settings.ADMIN_EMAILS,
            )
            admin_msg.attach_alternative(admin_html, "text/html")
            admin_msg.send(fail_silently=False)

            logger.info(f"📩 Payment confirmation email sent to admins: {settings.ADMIN_EMAILS}")

    except Exception as e:
        logger.error(f"❌ Failed to send program payment confirmation email: {str(e)}")

        
# views.py - Add these imports
from .models import ProgramPayment
from .serializers import ProgramPaymentSerializer
# views.py
@api_view(['POST'])
def initiate_program_payment(request, registration_id):
    """Initiate payment for program registration using ProgramPaymentService"""
    try:
        # Get the program registration
        registration = get_object_or_404(ProgramRegistration, id=registration_id)
        
        # Check if registration already has a payment
        if hasattr(registration, 'payment'):
            payment = registration.payment
            logger.info(f"✅ Using existing program payment: {payment.id}")
        else:
            # Create new payment
            payment = ProgramPayment.objects.create(
                registration=registration,
                customer_email=registration.email,
                customer_phone=registration.phone_number,
                description=f"Program: {registration.program.title}",
                payment_method='pesapal'
            )
            logger.info(f"✅ Created new program payment: {payment.id}")

        # Use ProgramPaymentService to initiate payment (with correct callback URL)
        program_payment_service = ProgramPaymentService()
        order_response = program_payment_service.submit_order(payment)

        if order_response and order_response.get('redirect_url'):
            # Update payment with PesaPal details
            payment.pesapal_order_tracking_id = order_response.get('order_tracking_id')
            payment.pesapal_payment_url = order_response.get('redirect_url')
            payment.payment_status = 'initiated'
            payment.payment_initiated_at = timezone.now()
            payment.save()
            
            logger.info(f"✅ Program payment initiated successfully - Payment ID: {payment.id}, Tracking ID: {payment.pesapal_order_tracking_id}")
            
            return Response({
                'payment_url': order_response.get('redirect_url'),
                'order_tracking_id': payment.pesapal_order_tracking_id,
                'payment_id': str(payment.id),
                'registration_id': registration.id,
                'message': 'Payment initiated successfully'
            })
        else:
            # Mark payment as failed if initiation fails
            payment.payment_status = 'failed'
            payment.save()
            
            logger.error(f"❌ Program payment initiation failed for registration: {registration.id}")
            return Response(
                {'error': 'Failed to initiate payment with PesaPal'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except ProgramRegistration.DoesNotExist:
        logger.error(f"❌ Program registration not found: {registration_id}")
        return Response(
            {'error': 'Program registration not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"❌ Program payment initiation error: {str(e)}")
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
            # Use ProgramPaymentService for consistency
            program_payment_service = ProgramPaymentService()
            status_response = program_payment_service.get_transaction_status(payment.pesapal_order_tracking_id)
            
            if status_response:
                logger.info(f"🔍 Program payment status check - Payment ID: {payment_id}, PesaPal Status: {status_response.get('status_code')}")
                return Response({
                    'payment_status': payment.payment_status,
                    'pesapal_status': status_response,
                    'payment_details': ProgramPaymentSerializer(payment).data
                })
        
        logger.info(f"🔍 Program payment status - Payment ID: {payment_id}, Status: {payment.payment_status}")
        return Response({
            'payment_status': payment.payment_status,
            'payment_details': ProgramPaymentSerializer(payment).data
        })
        
    except ProgramPayment.DoesNotExist:
        logger.error(f"❌ Program payment not found: {payment_id}")
        return Response(
            {'error': 'Program payment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"❌ Program payment status error: {str(e)}")
        return Response(
            {'error': f'Failed to get payment status: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
def send_program_payment_confirmation_email(payment):
    """Send payment confirmation email for program registration"""
    registration = payment.registration
    program = registration.program
    
    context = {
        'name': registration.full_name,
        'program': program.title,
        'amount': payment.amount,
        'currency': payment.currency,
        'transaction_id': payment.pesapal_transaction_id,
    }

    subject = f"✅ Payment Confirmed for {program.title}"
    html_content = render_to_string('emails/program_payment_confirmation.html', context)
    text_content = render_to_string('emails/program_payment_confirmation.txt', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[registration.email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)