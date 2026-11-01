"""
Capa de Servicios de Dominio (Domain Services).

Agrupa la lógica de negocio reusable e independiente del protocolo HTTP:
- `otp_service`: Ciclo de vida de códigos OTP de recuperación y envío SMTP.
- `sync_service`: Operaciones atómicas de sincronización offline (Push y Pull).
"""

from .otp_service import (
    enmascarar_correo,
    generar_codigo_numerico,
    solicitar_codigo_recuperacion,
    enviar_correo_otp,
    aplicar_cambio_pin,
)
from .sync_service import (
    procesar_push_sincronizacion,
    obtener_conjuntos_pull,
)

__all__ = [
    'enmascarar_correo',
    'generar_codigo_numerico',
    'solicitar_codigo_recuperacion',
    'enviar_correo_otp',
    'aplicar_cambio_pin',
    'procesar_push_sincronizacion',
    'obtener_conjuntos_pull',
]

