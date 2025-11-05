from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views



urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('accounts/auth/', include('dj_rest_auth.urls')),
    path('accounts/auth/registration/', include('dj_rest_auth.registration.urls')),
    path("accounts/", include("allauth.urls")),  # For social login
    
    path(
        "accounts/password/reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    
    
]

# 👇 Serve uploaded images (only in development)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
