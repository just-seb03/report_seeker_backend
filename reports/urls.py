"""
Enrutamiento de Endpoints REST de la API (`/api/v1/`).

Este módulo define las rutas de la API utilizadas por los clientes móviles y web:
- `DefaultRouter`: Expone endpoints CRUD navegables para `reportes` y `localizaciones`
  (utilizados por el visor de la API y herramientas externas de gestión).
- Endpoints de autenticación (`/auth/*`): Consumidos por la pantalla de inicio de sesión
  (`LoginScreen.tsx`), el modal de recuperación de clave (`PinRecoveryModal.tsx`)
  y el modal de actualización de perfil (`ChangeEmailModal.tsx`).
- Endpoints de sincronización (`/sync/*`): Consumidos por el motor de sincronización
  offline del cliente móvil (`SyncService.ts`).
- Endpoint de verificación de estado (`/health/`): Utilizado por balanceadores de carga,
  monitoreo de infraestructura y comprobación previa de conectividad.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from reports.views import (
    LoginView,
    SyncPushView,
    SyncPullView,
    VerifyWorkerView,
    PinRecoveryView,
    ChangeEmailView,
    RequestPinResetView,
    VerifyPinResetView,
    HealthCheckView,
    ReporteViewSet,
    LocalizacionViewSet,
    UsuarioViewSet,
)

# Router automático para la interfaz navegable de DRF y operaciones CRUD
router = DefaultRouter()
router.register('reportes', ReporteViewSet, basename='reporte')
router.register('localizaciones', LocalizacionViewSet, basename='localizacion')
router.register('usuarios', UsuarioViewSet, basename='usuario')

urlpatterns = [
    # Interfaz navegable y operaciones REST CRUD (/api/v1/reportes/, /api/v1/localizaciones/)
    path('', include(router.urls)),

    # Módulo de Autenticación y Credenciales (Login, recuperación de PIN y cambio de correo)
    path('auth/login/', LoginView.as_view(), name='api_auth_login'),
    path('auth/verify-worker/', VerifyWorkerView.as_view(), name='api_auth_verify_worker'),
    path('auth/pin-recovery/', PinRecoveryView.as_view(), name='api_auth_pin_recovery'),
    path('auth/request-pin-reset/', RequestPinResetView.as_view(), name='api_auth_request_pin_reset'),
    path('auth/verify-pin-reset/', VerifyPinResetView.as_view(), name='api_auth_verify_pin_reset'),
    path('auth/change-email/', ChangeEmailView.as_view(), name='api_auth_change_email'),

    # Módulo de Sincronización Offline Bidireccional (Consumido por SyncService en la app móvil)
    path('sync/push/', SyncPushView.as_view(), name='api_sync_push'),
    path('sync/pull/', SyncPullView.as_view(), name='api_sync_pull'),

    # Verificación de salud y monitoreo de conectividad
    path('health/', HealthCheckView.as_view(), name='api_health_check'),
]
