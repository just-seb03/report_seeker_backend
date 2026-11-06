"""
Módulo de Serializadores de la aplicación Reports.

Organizado por dominios para facilitar el mantenimiento y la modularidad:
- `common`: Campos personalizados compartidos (ej. Base64ImageField con validación binaria).
- `usuarios`: Serializadores de Usuario (público y completo con PIN para sincronización).
- `localizaciones`: Serializadores de Localizaciones y sectores de faena.
- `reportes`: Serializadores de Reporte, Historial, subida en lote y API navegable.
- `auth`: Serializadores para login, verificación de trabajadores y recuperación de PIN vía OTP.

Dónde se utiliza:
- Importado centralmente por los controladores en `reports/views/` y consumido por las pruebas automatizadas.
"""

from .common import Base64ImageField
from .usuarios import UsuarioSerializer, UsuarioPublicSerializer
from .localizaciones import LocalizacionSerializer
from .reportes import (
    ReporteHistorialItemSerializer,
    ReportePushItemSerializer,
    SyncPushPayloadSerializer,
    ReportePullSerializer,
    ReporteSerializer,
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
    'ReporteSerializer',
    'VerifyWorkerSerializer',
    'PinRecoverySerializer',
    'ChangeEmailSerializer',
    'RequestPinResetSerializer',
    'VerifyPinResetSerializer',
]

