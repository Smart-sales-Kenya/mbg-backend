from django.urls import path
from . import views

urlpatterns = [
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

    




]
