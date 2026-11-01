import base64
import re
import uuid
from typing import Optional
from django.core.files.base import ContentFile
from rest_framework import serializers
from .models import Usuario, Localizacion, Reporte, ReporteHistorial


class Base64ImageField(serializers.Field):
    """
    Campo personalizado de DRF para decodificar cadenas de imagen Base64
    (data:image/webp;base64,... o Base64 puro) en archivos ContentFile para
    ser almacenados en disco (MEDIA_ROOT).
    """
    def to_internal_value(self, data) -> Optional[ContentFile]:
        if not data:
            return None

        if not isinstance(data, str):
            raise serializers.ValidationError("El formato de la imagen debe ser un string Base64.")

        ext = 'webp'
        if 'base64,' in data:
            header, base64_data = data.split('base64,', 1)
            if 'image/webp' in header:
                ext = 'webp'
            elif 'image/png' in header:
                ext = 'png'
            elif 'image/jpeg' in header or 'image/jpg' in header:
                ext = 'jpg'
        else:
            base64_data = data

        try:
            decoded_bytes = base64.b64decode(base64_data)
        except Exception:
            raise serializers.ValidationError("Cadena Base64 inválida o corrupta.")

        filename = f"foto_{uuid.uuid4().hex[:10]}.{ext}"
        return ContentFile(decoded_bytes, name=filename)

    def to_representation(self, value) -> Optional[str]:
        if not value:
            return None
        request = self.context.get('request')
        if request and hasattr(value, 'url'):
            return request.build_absolute_uri(value.url)
        return getattr(value, 'url', None)


class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer completo de Usuario para descarga de catálogos (sincronización delta / pull).
    Incluye pin hasheado para permitir la autenticación offline en terreno por parte del móvil.
    """
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

    def get_foto_perfil(self, obj: Usuario) -> Optional[str]:
        if obj.foto_perfil:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.foto_perfil.url)
            return obj.foto_perfil.url
        return None


class UsuarioPublicSerializer(serializers.ModelSerializer):
    """
    Serializer público de Usuario para respuestas de login.
    """
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

    def get_foto_perfil(self, obj: Usuario) -> Optional[str]:
        if obj.foto_perfil:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.foto_perfil.url)
            return obj.foto_perfil.url
        return None


class LocalizacionSerializer(serializers.ModelSerializer):
    """
    Serializer de Localizacion para catálogos maestros.
    """
    class Meta:
        model = Localizacion
        fields = ['id', 'nombre', 'activo', 'updated_at']


class ReporteHistorialItemSerializer(serializers.Serializer):
    """
    Serializer para eventos de auditoría entrantes en sync/push.
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
    Serializer para reportes entrantes en sync/push.
    Acepta 'fotografia_base64' y la transforma en ContentFile.
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
    Payload contenedor para la subida en lote (reportes e historiales).
    """
    reportes = ReportePushItemSerializer(many=True, required=False, default=[])
    historial = ReporteHistorialItemSerializer(many=True, required=False, default=[])


class ReportePullSerializer(serializers.ModelSerializer):
    """
    Serializer para sincronización delta descendente (sync/pull).
    Resuelve la URL absoluta de la fotografía para que la app móvil la descargue.
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
        if obj.fotografia:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fotografia.url)
            return obj.fotografia.url
        return None

    def get_ubicacion_id(self, obj: Reporte) -> Optional[int]:
        return obj.localizacion_id if obj.localizacion else None

    def get_usuario_id(self, obj: Reporte) -> Optional[int]:
        return obj.usuario_id if obj.usuario else None


class VerifyWorkerSerializer(serializers.Serializer):
    """
    Valida si un trabajador existe y su correo coincide, antes de permitirle cambiar el PIN.
    """
    usuario_id = serializers.IntegerField(min_value=10000, max_value=99999)
    correo = serializers.EmailField()

    def validate(self, attrs):
        usuario_id = attrs.get('usuario_id')
        correo = attrs.get('correo', '').strip().lower()

        try:
            usuario = Usuario.objects.get(usuario_id=usuario_id, estado='activo')
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({'usuario_id': 'No existe un usuario activo con esta credencial.'})

        if usuario.correo.strip().lower() != correo:
            raise serializers.ValidationError({'correo': 'El correo no coincide con el registrado en el sistema.'})

        attrs['usuario'] = usuario
        return attrs


class PinRecoverySerializer(serializers.Serializer):
    """
    Permite a un trabajador restablecer su PIN de 4 dígitos.
    Acepta 'nuevo_pin' o 'pin', y 'correo' es opcional para compatibilidad con la app móvil.
    """
    usuario_id = serializers.IntegerField(min_value=10000, max_value=99999)
    correo = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    nuevo_pin = serializers.CharField(max_length=4, min_length=4, required=False)
    pin = serializers.CharField(max_length=4, min_length=4, required=False)

    def validate(self, attrs):
        usuario_id = attrs.get('usuario_id')
        raw_nuevo_pin = (
            attrs.get('nuevo_pin')
            or attrs.get('pin')
            or self.initial_data.get('nuevo_pin')
            or self.initial_data.get('pin')
        )

        if raw_nuevo_pin is None:
            raise serializers.ValidationError({'nuevo_pin': 'Debes proporcionar el nuevo PIN de 4 dígitos.'})

        pin_str = str(raw_nuevo_pin).strip()
        if not re.match(r'^\d{4}$', pin_str):
            raise serializers.ValidationError({'nuevo_pin': 'El PIN debe componerse exactamente de 4 dígitos numéricos.'})

        try:
            usuario = Usuario.objects.get(usuario_id=usuario_id, estado='activo')
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({'usuario_id': 'No existe un usuario activo con este ID.'})

        correo = attrs.get('correo')
        if correo:
            correo_clean = str(correo).strip().lower()
            if usuario.correo.strip().lower() != correo_clean:
                raise serializers.ValidationError({'correo': 'El correo no corresponde al usuario indicado.'})

        attrs['usuario'] = usuario
        attrs['nuevo_pin'] = pin_str
        return attrs


class ChangeEmailSerializer(serializers.Serializer):
    """
    Permite a un usuario autenticado por PIN actualizar su correo corporativo.
    """
    usuario_id = serializers.IntegerField(min_value=10000, max_value=99999)
    pin = serializers.CharField(max_length=128)
    nuevo_correo = serializers.EmailField()

    def validate_nuevo_correo(self, value):
        correo = value.strip().lower()
        usuario_id = self.initial_data.get('usuario_id')
        if Usuario.objects.filter(correo__iexact=correo).exclude(usuario_id=usuario_id).exists():
            raise serializers.ValidationError('Este correo corporativo ya se encuentra asignado a otro usuario.')
        return correo

    def validate(self, attrs):
        usuario_id = attrs.get('usuario_id')
        raw_pin = attrs.get('pin')

        try:
            usuario = Usuario.objects.get(usuario_id=usuario_id, estado='activo')
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({'usuario_id': 'Credenciales no válidas.'})

        if not usuario.check_pin(raw_pin):
            raise serializers.ValidationError({'pin': 'El PIN actual ingresado es incorrecto.'})

        attrs['usuario'] = usuario
        return attrs
