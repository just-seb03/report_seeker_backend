"""
Capa de Vistas y Controladores REST de la aplicación Reports.

Este paquete agrupa los controladores de la API organizados por dominios:
- `auth_views`: Login de operarios, verificación de personal, recuperación de PIN mediante OTP y portal web.
- `sync_views`: Mecanismo de sincronización offline-first (Push y Pull) para la aplicación móvil.
- `crud_views`: Controladores `ModelViewSet` para operaciones estándar navegables de reportes y localizaciones.
- `system_views`: Diagnóstico de salud y disponibilidad del servicio (Health Check).

Dónde se utiliza:
- Importado directamente por el enrutador central `reports/urls.py` y por las suites de pruebas automatizadas.
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
from .system_views import (
    HealthCheckView,
)
from .crud_views import (
    ReporteViewSet,
    LocalizacionViewSet,
    UsuarioViewSet,
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
    'HealthCheckView',
    'ReporteViewSet',
    'LocalizacionViewSet',
    'UsuarioViewSet',
    'enmascarar_correo',
]
