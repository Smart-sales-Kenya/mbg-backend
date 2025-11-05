from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView
from .views import MyTokenObtainPairView



urlpatterns = [
    
    path('', views.sign_in, name='sign_in'),
    path('sign-out', views.sign_out, name='sign_out'),
    path('auth-receiver', views.auth_receiver, name='auth_receiver'),
    
     # JWT Auth endpoints
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    path("get-csrf-token/", views.get_csrf_token, name="get_csrf_token"),
    path('hello/', views.hello_world),
    path('contact/', views.contact_view, name='contact'),
    path('team/', views.team_list, name='team-list'),
    path('gallery/', views.gallery_list, name='gallery_list'),
    path('gallery/categories/', views.category_list, name='category_list'),
    path('testimonials/', views.get_testimonials, name='testimonial-list'),
    
     # Event endpoints
    path('events/', views.event_list, name='api-events-list'),
    path('events/<int:pk>/', views.event_detail, name='api-event-detail'),

    # Event registration endpoints
    path('registrations/', views.event_registration_list, name='api-registrations'),
    path('events/<int:event_id>/registrations/', views.event_registration_by_event, name='api-registrations-by-event'),
    
    path('program/register/', views.program_register_endpoint, name='program-register'),
    path('program/list/', views.program_list_endpoint, name='program-list'),

    




]
