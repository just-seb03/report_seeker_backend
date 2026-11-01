"""
Serializadores para flujos de autenticación, verificación de trabajadores y recuperación de PIN.
"""

import re
from django.utils import timezone
from rest_framework import serializers
from reports.models import Usuario


class VerifyWorkerSerializer(serializers.Serializer):
    """
    Valida la existencia de un trabajador activo a partir de su ID y correo registrado.
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
    Permite restablecer el PIN de 4 dígitos de un trabajador activo.
    
    Acepta tanto 'nuevo_pin' como 'pin' como claves de entrada para retrocompatibilidad.
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
    Permite a un usuario autenticado mediante su PIN actualizar su correo corporativo.
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


class RequestPinResetSerializer(serializers.Serializer):
    """
    Valida la solicitud de generación de código OTP de 6 dígitos.
    
    No requiere ingresar el correo por motivos de seguridad; el sistema despacha el código
    automáticamente al correo corporativo registrado asociado al usuario_id.
    """
    usuario_id = serializers.IntegerField(min_value=10000, max_value=99999)
    correo = serializers.EmailField(required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        usuario_id = attrs.get('usuario_id')

        try:
            usuario = Usuario.objects.get(usuario_id=usuario_id, estado='activo')
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({'usuario_id': 'No existe un usuario activo con esta credencial.'})

        attrs['usuario'] = usuario
        return attrs


class VerifyPinResetSerializer(serializers.Serializer):
    """
    Valida el código OTP de 6 dígitos ingresado por el usuario y el nuevo PIN de 4 dígitos.
    
    Protecciones incorporadas:
    - Verificación de formato numérico de 6 dígitos para OTP y 4 dígitos para PIN.
    - Expiración temporal (15 minutos).
    - Límite de 5 intentos fallidos para prevenir ataques de fuerza bruta.
    """
    usuario_id = serializers.IntegerField(min_value=10000, max_value=99999)
    codigo = serializers.CharField(max_length=6, min_length=6)
    nuevo_pin = serializers.CharField(max_length=4, min_length=4, required=False)
    pin = serializers.CharField(max_length=4, min_length=4, required=False)

    def validate(self, attrs):
        usuario_id = attrs.get('usuario_id')
        codigo = str(attrs.get('codigo', '')).strip()

        raw_nuevo_pin = (
            attrs.get('nuevo_pin')
            or attrs.get('pin')
            or self.initial_data.get('nuevo_pin')
            or self.initial_data.get('pin')
        )

        if raw_nuevo_pin is None:
            raise serializers.ValidationError({'nuevo_pin': 'Debes ingresar el nuevo PIN de 4 dígitos.'})

        pin_str = str(raw_nuevo_pin).strip()
        if not re.match(r'^\d{4}$', pin_str):
            raise serializers.ValidationError({'nuevo_pin': 'El nuevo PIN debe componerse exactamente de 4 dígitos numéricos.'})

        if not re.match(r'^\d{6}$', codigo):
            raise serializers.ValidationError({'codigo': 'El código de verificación debe contener 6 dígitos numéricos.'})

        try:
            usuario = Usuario.objects.get(usuario_id=usuario_id, estado='activo')
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({'usuario_id': 'No existe un usuario activo con este ID.'})

        # Buscar el código OTP pendiente más reciente
        otp = usuario.codigos_verificacion.filter(utilizado=False).order_by('-created_at').first()

        if not otp:
            raise serializers.ValidationError({'codigo': 'No hay ningún código de recuperación pendiente o ya fue utilizado.'})

        if timezone.now() > otp.expira_en:
            otp.utilizado = True
            otp.save(update_fields=['utilizado'])
            raise serializers.ValidationError({'codigo': 'El código de verificación ha expirado. Solicita uno nuevo.'})

        if otp.intentos >= 5:
            otp.utilizado = True
            otp.save(update_fields=['utilizado'])
            raise serializers.ValidationError({'codigo': 'Has superado el límite de intentos permitidos. Solicita un nuevo código.'})

        if otp.codigo != codigo:
            otp.intentos += 1
            otp.save(update_fields=['intentos'])
            restantes = 5 - otp.intentos
            raise serializers.ValidationError({
                'codigo': f'Código de verificación incorrecto. Intentos restantes: {restantes}.'
            })

        attrs['usuario'] = usuario
        attrs['otp_obj'] = otp
        attrs['nuevo_pin'] = pin_str
        return attrs

