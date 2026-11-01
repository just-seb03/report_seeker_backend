"""
Módulo de Serializadores de la aplicación Reports.

Organizado por dominios para facilitar el mantenimiento y lectura:
- `common`: Campos personalizados compartidos (ej. Base64ImageField).
- `usuarios`: Serializadores de Usuario (público y completo con PIN).
- `localizaciones`: Serializadores de Localizaciones y sectores.
- `reportes`: Serializadores de Reporte, Historial y payloads de sincronización.
- `auth`: Serializadores para login, verificación de trabajadores y recuperación de PIN vía OTP.
"""

from .common import Base64ImageField
from .usuarios import UsuarioSerializer, UsuarioPublicSerializer
from .localizaciones import LocalizacionSerializer
from .reportes import (
    ReporteHistorialItemSerializer,
    ReportePushItemSerializer,
    SyncPushPayloadSerializer,
    ReportePullSerializer,
)
from .auth import (
    VerifyWorkerSerializer,
    PinRecoverySerializer,
    ChangeEmailSerializer,
    RequestPinResetSerializer,
    VerifyPinResetSerializer,
)

__all__ = [
    'Base64ImageField',
    'UsuarioSerializer',
    'UsuarioPublicSerializer',
    'LocalizacionSerializer',
    'ReporteHistorialItemSerializer',
    'ReportePushItemSerializer',
    'SyncPushPayloadSerializer',
    'ReportePullSerializer',
    'VerifyWorkerSerializer',
    'PinRecoverySerializer',
    'ChangeEmailSerializer',
    'RequestPinResetSerializer',
    'VerifyPinResetSerializer',
]

