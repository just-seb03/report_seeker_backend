import base64
import uuid
from django.core.files.base import ContentFile
from rest_framework import serializers
from .models import Usuario, Localizacion, Reporte, ReporteHistorial


class UsuarioSerializer(serializers.ModelSerializer):
    foto_perfil = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            'usuario_id',
            'nombre',
            'correo',
            'cargo',
            'foto_perfil',
            'pin',
            'habilitar_sumario',
            'estado',
            'updated_at',
        ]

    def get_foto_perfil(self, obj):
        if obj.foto_perfil:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.foto_perfil.url)
            return obj.foto_perfil.url
        return None


class UsuarioPublicSerializer(serializers.ModelSerializer):
    foto_perfil = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            'usuario_id',
            'nombre',
            'correo',
            'cargo',
            'habilitar_sumario',
            'foto_perfil',
        ]

    def get_foto_perfil(self, obj):
        if obj.foto_perfil:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.foto_perfil.url)
            return obj.foto_perfil.url
        return None


class LocalizacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Localizacion
        fields = ['id', 'nombre', 'activo', 'updated_at']


class ReporteHistorialItemSerializer(serializers.Serializer):
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
    local_id = serializers.IntegerField(required=False)
    uuid = serializers.UUIDField(required=True)
    titulo = serializers.CharField(max_length=255)
    descripcion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fotografia_base64 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fecha_captura = serializers.DateTimeField()
    usuario_id = serializers.IntegerField(required=False, allow_null=True)
    usuario_nombre = serializers.CharField(max_length=150, required=False, allow_blank=True)
    usuario_cargo = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    ubicacion = serializers.CharField(max_length=150, required=False, allow_blank=True)
    ubicacion_id = serializers.IntegerField(required=False, allow_null=True)
    prioridad = serializers.ChoiceField(choices=['Alta', 'Media', 'Baja'], default='Media')
    estado = serializers.CharField(default='capturado')


class SyncPushPayloadSerializer(serializers.Serializer):
    reportes = ReportePushItemSerializer(many=True, required=False, default=[])
    historial = ReporteHistorialItemSerializer(many=True, required=False, default=[])


class ReportePullSerializer(serializers.ModelSerializer):
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

    def get_fotografia_url(self, obj):
        if obj.fotografia:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fotografia.url)
            return obj.fotografia.url
        return None

    def get_ubicacion_id(self, obj):
        return obj.localizacion_id if obj.localizacion else None

    def get_usuario_id(self, obj):
        return obj.usuario_id if obj.usuario else None


def decode_base64_file(data_str: str, file_prefix: str = "img"):
    """
    Decodifica un string base64 (data URI o base64 puro) y retorna un ContentFile.
    """
    if not data_str or not isinstance(data_str, str):
        return None

    if 'base64,' in data_str:
        header, base64_data = data_str.split('base64,', 1)
        # Extraer extensión si está presente
        if 'image/webp' in header:
            ext = 'webp'
        elif 'image/png' in header:
            ext = 'png'
        elif 'image/jpeg' in header or 'image/jpg' in header:
            ext = 'jpg'
        else:
            ext = 'webp'
    else:
        base64_data = data_str
        ext = 'webp'

    try:
        decoded_bytes = base64.b64decode(base64_data)
        file_name = f"{file_prefix}_{uuid.uuid4().hex[:8]}.{ext}"
        return ContentFile(decoded_bytes, name=file_name)
    except Exception as e:
        return None

