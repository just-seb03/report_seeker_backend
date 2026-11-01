"""
Capa de Vistas y Controladores REST de la aplicación Reports.

Organizado por áreas de responsabilidad:
- `auth_views`: Login, verificación de trabajadores, recuperación OTP de PIN y portal web.
- `sync_views`: Protocolo de sincronización móvil offline-first (Push y Pull).
"""

from .auth_views import (
    LoginView,
    VerifyWorkerView,
    PinRecoveryView,
    ChangeEmailView,
    RequestPinResetView,
    VerifyPinResetView,
    AuthPortalWebView,
)
from .sync_views import (
    SyncPushView,
    SyncPullView,
)
from reports.services.otp_service import enmascarar_correo

__all__ = [
    'LoginView',
    'VerifyWorkerView',
    'PinRecoveryView',
    'ChangeEmailView',
    'RequestPinResetView',
    'VerifyPinResetView',
    'AuthPortalWebView',
    'SyncPushView',
    'SyncPullView',
    'enmascarar_correo',
]

