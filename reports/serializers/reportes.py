"""
Serializadores para Reportes de incidencias y eventos de bitácora/auditoría.
"""

from typing import Optional
from rest_framework import serializers
from reports.models import Reporte
from .common import Base64ImageField


class ReporteHistorialItemSerializer(serializers.Serializer):
    """
    Validador de eventos de bitácora y cambios entrantes en el lote de `sync/push`.
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
    Validador de reportes individuales entrantes en el lote de `sync/push`.
    
    Acepta 'fotografia_base64' para ser decodificada y guardada en disco.
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
    Payload contenedor para la subida en lote de reportes y eventos de historial.
    """
    reportes = ReportePushItemSerializer(many=True, required=False, default=[])
    historial = ReporteHistorialItemSerializer(many=True, required=False, default=[])


class ReportePullSerializer(serializers.ModelSerializer):
    """
    Serializer para sincronización delta descendente (servidor -> móvil).
    
    Resuelve la URL pública de la fotografía y desnormaliza los campos de usuario y ubicación.
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

