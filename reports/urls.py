"""
Enrutamiento de Endpoints REST de la API de Faena (`/api/v1/`).

Rutas disponibles:
- `auth/login/`: Validación de credenciales y expedición de tokens DRF.
- `auth/verify-worker/`: Comprobación previa de existencia de trabajador.
- `auth/pin-recovery/`: Restablecimiento de PIN.
- `auth/request-pin-reset/`: Solicitud y despacho de código OTP de 6 dígitos por correo.
- `auth/verify-pin-reset/`: Verificación de código OTP y actualización segura de PIN.
- `auth/change-email/`: Actualización de correo corporativo mediante PIN.
- `sync/push/`: Sincronización ascendente en lote (móvil -> servidor).
- `sync/pull/`: Sincronización descendente incremental (servidor -> móvil).
"""

from django.urls import path
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
)

urlpatterns = [
    # --- Módulo de Autenticación y Gestión de Credenciales ---
    path('auth/login/', LoginView.as_view(), name='api_auth_login'),
    path('auth/verify-worker/', VerifyWorkerView.as_view(), name='api_auth_verify_worker'),
    path('auth/pin-recovery/', PinRecoveryView.as_view(), name='api_auth_pin_recovery'),
    path('auth/request-pin-reset/', RequestPinResetView.as_view(), name='api_auth_request_pin_reset'),
    path('auth/verify-pin-reset/', VerifyPinResetView.as_view(), name='api_auth_verify_pin_reset'),
    path('auth/change-email/', ChangeEmailView.as_view(), name='api_auth_change_email'),

    # --- Módulo de Sincronización Offline Bidireccional ---
    path('sync/push/', SyncPushView.as_view(), name='api_sync_push'),
    path('sync/pull/', SyncPullView.as_view(), name='api_sync_pull'),

    # --- Módulo de Salud y Monitoreo del Sistema ---
    path('health/', HealthCheckView.as_view(), name='api_health_check'),
]
