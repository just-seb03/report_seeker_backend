"""
Controladores de Autenticación, Credenciales y Gestión de PIN.

Este módulo expone los endpoints REST para:
- Inicio de sesión con credencial de faena (usuario_id + PIN).
- Verificación de operarios activos.
- Solicitud de código OTP de 6 dígitos por correo para recuperación de PIN.
- Verificación del código OTP y actualización segura de PIN.
- Cambio de correo corporativo.
- Vista web del portal de autoservicio para faena.
"""

import logging
from django.contrib.auth.models import User
from django.core.cache import cache
from django.shortcuts import render
from django.views.generic import View
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.models import Usuario
from reports.serializers import (
    UsuarioPublicSerializer,
    VerifyWorkerSerializer,
    PinRecoverySerializer,
    ChangeEmailSerializer,
    RequestPinResetSerializer,
    VerifyPinResetSerializer,
)
from reports.services import (
    enmascarar_correo,
    solicitar_codigo_recuperacion,
    aplicar_cambio_pin,
)

logger = logging.getLogger(__name__)


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    
    Valida credenciales de faena (usuario_id + pin) y retorna token de sesión DRF
    junto con los datos del perfil público del operario.
    
    Seguridad (Fase 1 y Fase 2):
    - `throttle_scope = 'login'`: Límite estricto por IP (máx. 15/min) para mitigar fuerza bruta (SEC-02).
    - Bloqueo Progresivo de Cuenta (Account Lockout): Bloquea el usuario durante 5 minutos
      tras 5 intentos fallidos consecutivos de PIN (neutraliza ataques distribuidos multi-IP).
    
    Especificación: BACKEND_SPEC.md § 4.1
    """
    permission_classes = [AllowAny]
    throttle_scope = 'login'

    MAX_INTENTOS_FALLIDOS = 5
    TIEMPO_BLOQUEO_SEGUNDOS = 300  # 5 minutos

    def post(self, request):
        usuario_id = request.data.get('usuario_id')
        pin = request.data.get('pin')

        if not usuario_id or not pin:
            return Response(
                {'error': 'Se requieren usuario_id y pin.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Comprobar si la cuenta está en período de bloqueo por fuerza bruta
        lockout_key = f"login_lockout_{usuario_id}"
        fails_key = f"login_fails_{usuario_id}"

        if cache.get(lockout_key):
            return Response(
                {
                    'error': 'Cuenta temporalmente bloqueada por superar el límite de 5 intentos fallidos. '
                             'Por seguridad, intenta nuevamente en 5 minutos.'
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        try:
            usuario = Usuario.objects.get(usuario_id=usuario_id, estado='activo')
        except Usuario.DoesNotExist:
            return Response(
                {'error': 'Credenciales inválidas o usuario inactivo.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 2. Validar PIN
        if not usuario.check_pin(str(pin)):
            intentos_previos = cache.get(fails_key, 0) + 1
            if intentos_previos >= self.MAX_INTENTOS_FALLIDOS:
                cache.set(lockout_key, True, timeout=self.TIEMPO_BLOQUEO_SEGUNDOS)
                cache.delete(fails_key)
                return Response(
                    {
                        'error': 'Has superado el límite de 5 intentos fallidos. Tu cuenta ha sido bloqueada '
                                 'temporalmente durante 5 minutos.'
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            else:
                cache.set(fails_key, intentos_previos, timeout=self.TIEMPO_BLOQUEO_SEGUNDOS)
                restantes = self.MAX_INTENTOS_FALLIDOS - intentos_previos
                return Response(
                    {
                        'error': f'Credenciales inválidas o usuario inactivo. Intentos restantes antes del bloqueo: {restantes}.'
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )

        # 3. Login exitoso: limpiar contadores de intentos fallidos
        cache.delete(fails_key)
        cache.delete(lockout_key)

        # Vincular o crear usuario estándar de Django para generar token DRF
        django_user, _ = User.objects.get_or_create(
            username=str(usuario.usuario_id),
            defaults={'first_name': usuario.nombre, 'email': usuario.correo}
        )
        token, _ = Token.objects.get_or_create(user=django_user)

        user_data = UsuarioPublicSerializer(usuario, context={'request': request}).data

        return Response({
            'token': token.key,
            'usuario': user_data
        }, status=status.HTTP_200_OK)


class VerifyWorkerView(APIView):
    """
    POST /api/v1/auth/verify-worker/
    
    Valida si el ID y correo corresponden a un usuario activo registrado en faena.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyWorkerSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'valido': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario = serializer.validated_data['usuario']
        return Response({
            'valido': True,
            'usuario_id': usuario.usuario_id,
            'nombre': usuario.nombre,
            'cargo': usuario.cargo,
        }, status=status.HTTP_200_OK)


class PinRecoveryView(APIView):
    """
    POST /api/v1/auth/pin-recovery/
    
    Restablece el PIN del usuario activo previa validación de su identificador.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PinRecoverySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data['usuario']
        nuevo_pin = serializer.validated_data['nuevo_pin']

        usuario.set_pin(nuevo_pin)
        usuario.save(update_fields=['pin', 'updated_at'])

        # Sincronizar contraseña de Django User (para autenticación DRF)
        django_user, _ = User.objects.get_or_create(
            username=str(usuario.usuario_id),
            defaults={'first_name': usuario.nombre, 'email': usuario.correo}
        )
        django_user.set_password(nuevo_pin)
        django_user.save()

        return Response({
            'status': 'success',
            'message': 'PIN actualizado con éxito. Ya puedes ingresar en la app con tu nueva clave.',
            'usuario_id': usuario.usuario_id,
            'pin': nuevo_pin,
        }, status=status.HTTP_200_OK)


class ChangeEmailView(APIView):
    """
    POST /api/v1/auth/change-email/
    
    Actualiza el correo corporativo del trabajador tras validar su PIN de seguridad.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ChangeEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data['usuario']
        nuevo_correo = serializer.validated_data['nuevo_correo']

        usuario.correo = nuevo_correo
        usuario.save(update_fields=['correo', 'updated_at'])

        # Mantener sincronizado User de Django si existe
        User.objects.filter(username=str(usuario.usuario_id)).update(email=nuevo_correo)

        return Response({
            'status': 'success',
            'message': 'Correo corporativo actualizado exitosamente.',
            'usuario_id': usuario.usuario_id,
            'correo': nuevo_correo,
        }, status=status.HTTP_200_OK)


class RequestPinResetView(APIView):
    """
    POST /api/v1/auth/request-pin-reset/
    
    Genera un código OTP de 6 dígitos y lo envía al correo corporativo del trabajador
    para permitir la recuperación de su PIN de acceso de forma segura.
    
    Seguridad:
    - `throttle_scope = 'otp_request'`: Previene saturación del servidor SMTP (Brevo)
      y ataques de tipo Mail-Bombing mediante control de tasa de solicitudes (SEC-04).
    """
    permission_classes = [AllowAny]
    throttle_scope = 'otp_request'

    def post(self, request):
        serializer = RequestPinResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data.get('usuario')
        usuario_id = serializer.validated_data.get('usuario_id')

        # Si el usuario existe, enviar OTP a su casilla corporativa
        if usuario is not None:
            try:
                solicitar_codigo_recuperacion(usuario, duracion_minutos=15)
            except Exception as e:
                logger.error(f"Fallo al enviar correo OTP a {usuario.correo}: {e}")
                return Response({
                    'status': 'error',
                    'message': 'No se pudo conectar con el servidor de correo. Verifica tu conexión a internet.',
                    'error_detail': str(e)
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Mitigación SEC-04: Respuesta unificada neutral
        # Retorna el mismo status 200 OK tanto si el usuario existe como si no,
        # impidiendo a un atacante mapear qué números de credencial están activos.
        correo_display = enmascarar_correo(usuario.correo) if usuario else '******@******'

        return Response({
            'status': 'success',
            'message': 'Si la credencial ingresada es válida y activa, se ha enviado un código de verificación al correo corporativo registrado.',
            'usuario_id': usuario_id,
            'correo_enmascarado': correo_display,
            'expira_en_minutos': 15,
        }, status=status.HTTP_200_OK)


class VerifyPinResetView(APIView):
    """
    POST /api/v1/auth/verify-pin-reset/
    
    Comprueba el código OTP de 6 dígitos recibido por correo y actualiza el PIN del usuario.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyPinResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data['usuario']
        otp_obj = serializer.validated_data['otp_obj']
        nuevo_pin = serializer.validated_data['nuevo_pin']

        # Aplicar el cambio de PIN mediante el servicio de dominio
        aplicar_cambio_pin(usuario, otp_obj, nuevo_pin)

        return Response({
            'status': 'success',
            'message': 'PIN actualizado con éxito. Ya puedes ingresar en la app con tu nueva clave.',
            'usuario_id': usuario.usuario_id,
            'pin': nuevo_pin,
        }, status=status.HTTP_200_OK)


class AuthPortalWebView(View):
    """
    GET /auth/portal/
    
    Renderiza la interfaz web de autoservicio para recuperación de PIN y cambio de correo en faena.
    """
    def get(self, request):
        return render(request, 'reports/auth_portal.html')

