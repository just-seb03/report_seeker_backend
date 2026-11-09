"""
Serializadores para Reportes de incidencias, eventos de bitácora/auditoría y sincronización.

Este módulo provee las estructuras de serialización y deserialización para incidencias:
- `ReporteHistorialItemSerializer`: Valida eventos de auditoría (cambios de campo, autor, fechas).
- `ReportePushItemSerializer`: Valida cada reporte enviado en la sincronización en lote (`sync/push`),
  manejando la decodificación de fotos en Base64.
- `SyncPushPayloadSerializer`: Contenedor para el conjunto de reportes e historiales subidos por el móvil.
- `ReportePullSerializer`: Serializa reportes desde el servidor hacia el cliente móvil (`sync/pull`),
  construyendo URLs públicas absolutas para las fotografías.
- `ReporteSerializer`: Serializador completo de modelo para operaciones CRUD navegables.

Dónde se utiliza:
- En `reports/views/sync_views.py` para la sincronización con el cliente móvil (`SyncService.ts`).
- En `reports/views/crud_views.py` para la API REST navegable (`/api/v1/reportes/`).
"""

from typing import Optional
from rest_framework import serializers
from reports.models import Reporte
from .common import Base64ImageField


class ReporteHistorialItemSerializer(serializers.Serializer):
    """
    Validador de eventos individuales de bitácora y cambios de estado en lote (`sync/push`).
    
    Dónde se utiliza:
    - En `SyncPushPayloadSerializer` para procesar la lista `historial` enviada por el móvil.
    """
    local_id = serializers.IntegerField(required=False)
    uuid = serializers.UUIDField(required=True)
    reporte_uuid = serializers.UUIDField(required=True)
    usuario_id = serializers.IntegerField(required=False, allow_null=True)
    usuario_nombre = serializers.CharField(max_length=150)
    campo_modificado = serializers.CharField(max_length=50)
    valor_anterior = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    valor_nuevo = serializers.CharField(allow_blank=True)
    fecha_cambio = serializers.DateTimeField()


class ReportePushItemSerializer(serializers.Serializer):
    """
    Validador de incidencias individuales enviadas por el dispositivo móvil en lote (`sync/push`).
    
    Acepta el campo 'fotografia_base64' para ser decodificado y persistido en almacenamiento local.
    
    Dónde se utiliza:
    - En `SyncPushPayloadSerializer` para procesar la lista `reportes` enviada por el móvil.
    """
    local_id = serializers.IntegerField(required=False)
    uuid = serializers.UUIDField(required=True)
    titulo = serializers.CharField(max_length=255)
    descripcion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fotografia_base64 = Base64ImageField(required=False, allow_null=True)
    fecha_captura = serializers.DateTimeField()
    usuario_id = serializers.IntegerField(required=False, allow_null=True)
    usuario_nombre = serializers.CharField(max_length=150, required=False, allow_blank=True)
    usuario_cargo = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    ubicacion = serializers.CharField(max_length=150, required=False, allow_blank=True)
    ubicacion_id = serializers.IntegerField(required=False, allow_null=True)
    prioridad = serializers.ChoiceField(choices=['Alta', 'Media', 'Baja'], default='Media')
    estado = serializers.CharField(default='capturado')


class SyncPushPayloadSerializer(serializers.Serializer):
    """
    Payload contenedor para la subida masiva e idempotente de reportes y bitácoras.
    
    Dónde se utiliza:
    - En `SyncPushView` (`/api/v1/sync/push/`), consumido directamente por `SyncService.ts`.
    """
    reportes = ReportePushItemSerializer(many=True, required=False, default=[])
    historial = ReporteHistorialItemSerializer(many=True, required=False, default=[])


class ReportePullSerializer(serializers.ModelSerializer):
    """
    Serializador delta descendente para enviar reportes desde el servidor hacia el móvil.
    
    Resuelve la URL pública absoluta de las fotografías y desnormaliza campos de autor y localización.
    
    Dónde se utiliza:
    - En `SyncPullView` (`/api/v1/sync/pull/`), consumido por `SyncService.ts` para
      actualizar el almacenamiento local SQLite del teléfono.
    """
    fotografia_url = serializers.SerializerMethodField()
    ubicacion = serializers.CharField(source='ubicacion_texto', read_only=True)
    ubicacion_id = serializers.SerializerMethodField()
    usuario_id = serializers.SerializerMethodField()

    class Meta:
        model = Reporte
        fields = [
            'uuid',
            'titulo',
            'descripcion',
            'fotografia_url',
            'fecha_captura',
            'usuario_id',
            'usuario_nombre',
            'usuario_cargo',
            'ubicacion',
            'ubicacion_id',
            'prioridad',
            'estado',
            'updated_at',
        ]

    def get_fotografia_url(self, obj: Reporte) -> Optional[str]:
        """Obtiene la URL pública completa de la fotografía para que la app móvil la descargue."""
        if obj.fotografia:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fotografia.url)
            return obj.fotografia.url
        return None

    def get_ubicacion_id(self, obj: Reporte) -> Optional[int]:
        """Obtiene el ID de la ubicación formal asociada si existe."""
        return obj.localizacion_id if obj.localizacion else None

    def get_usuario_id(self, obj: Reporte) -> Optional[int]:
        """Obtiene el ID del usuario autor si existe."""
        return obj.usuario_id if obj.usuario else None


class ReporteSerializer(serializers.ModelSerializer):
    """
    Serializador integral basado en ModelSerializer para el modelo Reporte.
    
    Mapea automáticamente los campos del modelo para permitir operaciones completas
    (GET, POST, PUT, PATCH, DELETE) en la API REST navegable.
    
    Dónde se utiliza:
    - En `ReporteViewSet` (`/api/v1/reportes/`), utilizado en la interfaz web de DRF
      y por herramientas externas de supervisión.
    """
    localizacion_nombre = serializers.CharField(
        source='localizacion.nombre',
        read_only=True,
    )

    class Meta:
        model = Reporte
        fields = [
            'id',
            'uuid',
            'titulo',
            'descripcion',
            'fotografia',
            'fecha_captura',
            'usuario',
            'usuario_nombre',
            'usuario_cargo',
            'localizacion',
            'localizacion_nombre',
            'ubicacion_texto',
            'prioridad',
            'estado',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']

