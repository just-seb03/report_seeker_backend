"""
Configuración de URLs Globales del Proyecto Report Seeker Backend.

Rutas principales:
- `/admin/`: Panel de Control y Auditoría de Django para supervisores.
- `/api-auth/`: Autenticación de sesión interactiva (Login/Logout) para DRF Browsable API.
- `/auth/portal/`: Portal Web de Autoservicio para recuperación de PIN.
- `/api/v1/`: Endpoints REST para la app móvil en faena (autenticación y sync).
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from reports.views import AuthPortalWebView

urlpatterns = [
    # Panel Administrativo Central
    path('admin/', admin.site.urls),

    # Autenticación de sesión interactiva en la interfaz navegable (DRF Browsable API)
    path('api-auth/', include('rest_framework.urls')),

    # Portal Web de Autoservicio
    path('auth/portal/', AuthPortalWebView.as_view(), name='auth_portal_web'),

    # API REST v1 para la App Móvil
    path('api/v1/', include('reports.urls')),
]

# Servir archivos estáticos y multimedia en entorno de desarrollo local
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
