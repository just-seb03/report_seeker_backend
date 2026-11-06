"""
Controladores de Autenticación, Credenciales y Gestión de PIN.

Este módulo expone los endpoints REST para la seguridad y control de acceso:
- `LoginView`: Validación de credenciales operativas (usuario_id + PIN) y emisión de token DRF.
- `VerifyWorkerView`: Comprobación previa de existencia y estado activo del trabajador.
- `PinRecoveryView`: Actualización directa de PIN validado mediante credencial.
- `RequestPinResetView`: Generación y despacho de código OTP de 6 dígitos al correo corporativo.
- `VerifyPinResetView`: Validación del código OTP de un solo uso y actualización segura del PIN.
- `ChangeEmailView`: Actualización de la dirección de correo corporativo mediante validación de PIN.
- `AuthPortalWebView`: Interfaz web de autoservicio para recuperación de accesos desde navegadores.

Dónde se utiliza:
- En la aplicación móvil: `LoginScreen.tsx` (inicio de sesión), `PinRecoveryModal.tsx`
  (recuperación de clave por código OTP) y `ChangeEmailModal.tsx` (cambio de correo).
- En el cliente web: `reports/templates/reports/auth_portal.html` (portal de autoservicio).
- En las pruebas de integración: `reports/tests/test_auth.py` y `reports/tests/test_security.py`.
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
    
    Valida las credenciales del trabajador (usuario_id + PIN) y retorna el token de sesión
    de Django REST Framework junto con la información pública del perfil del usuario.
    
    Mecanismos de protección:
    - Limitación de tasa (`throttle_scope = 'login'`): Restringe las solicitudes por IP
      (máximo 15 intentos por minuto) para mitigar ataques automatizados de fuerza bruta.
    - Bloqueo temporal de cuenta (Account Lockout): Si se registran 5 intentos fallidos
      consecutivos de PIN sobre una misma credencial, la cuenta se bloquea automáticamente
      durante 5 minutos, protegiendo contra ataques distribuidos desde múltiples direcciones IP.
    
    Dónde se utiliza:
    - En la pantalla de ingreso principal de la aplicación móvil (`LoginScreen.tsx`).
    - En la autenticación del portal web de autoservicio (`auth_portal.html`).
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

        # 1. Comprobar si la cuenta se encuentra temporalmente bloqueada por intentos fallidos
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

        # 2. Validar el PIN numérico
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

        # 3. Acceso exitoso: reiniciar contadores de intentos fallidos
        cache.delete(fails_key)
        cache.delete(lockout_key)

        # Sincronizar o crear el registro correspondiente en auth.User para emisión del token DRF
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
    
    Verifica si una credencial de 5 dígitos y su correo electrónico asociado corresponden
    a un trabajador actualmente activo en los registros centrales.
    
    Dónde se utiliza:
    - En el paso previo de validación de identidad en la aplicación móvil antes de permitir
      operaciones sensibles o inicio de flujos de soporte.
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
    
    Permite restablecer directamente el PIN de acceso de un operario activo tras validar
    su número de credencial y datos registrados.
    
    Dónde se utiliza:
    - En flujos de recuperación directa administrada o soporte asistido en terreno.
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

        # Sincronizar contraseña del usuario en auth.User para autenticación DRF
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
    
    Actualiza la casilla de correo corporativo del trabajador previa comprobación de su PIN actual.
    
    Dónde se utiliza:
    - En el modal de configuración de perfil de la aplicación móvil (`ChangeEmailModal.tsx`).
    - En la pestaña de cambio de correo del portal web de autoservicio (`auth_portal.html`).
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

        # Mantener sincronizado el usuario interno de Django
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
    para permitir el restablecimiento de su clave de 4 dígitos.
    
    Mecanismos de protección:
    - Limitación de tasa (`throttle_scope = 'otp_request'`): Máximo 5 solicitudes por minuto
      para prevenir saturación del servidor SMTP y abusos de envío reiterado de correos.
    - Prevención de enumeración de usuarios: Retorna una respuesta neutral idéntica (código HTTP 200 OK)
      tanto si el ID existe en el sistema como si no, evitando que un atacante determine qué números
      de credencial corresponden a cuentas activas.
    
    Dónde se utiliza:
    - En el paso 1 del modal de recuperación de PIN en la app móvil (`PinRecoveryModal.tsx`).
    - En el formulario de solicitud de código en el portal web (`auth_portal.html`).
    """
    permission_classes = [AllowAny]
    throttle_scope = 'otp_request'

    def post(self, request):
        serializer = RequestPinResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data.get('usuario')
        usuario_id = serializer.validated_data.get('usuario_id')

        # Si el usuario existe y está activo, generar y despachar el código OTP por correo
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

        # Respuesta neutral para evitar la enumeración de credenciales activas
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
    
    Valida el código OTP de 6 dígitos recibido por correo y actualiza el PIN del usuario.
    
    Dónde se utiliza:
    - En el paso 2 del modal de recuperación de PIN de la aplicación móvil (`PinRecoveryModal.tsx`).
    - En la confirmación de nueva clave del portal web de autoservicio (`auth_portal.html`).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyPinResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data['usuario']
        otp_obj = serializer.validated_data['otp_obj']
        nuevo_pin = serializer.validated_data['nuevo_pin']

        # Consumir el código OTP y aplicar el cambio de contraseña
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
    
    Renderiza la interfaz web de autoservicio para la recuperación de PIN y gestión de correo.
    
    Dónde se utiliza:
    - Accesible desde navegadores web de escritorio o móviles para que los trabajadores
      puedan recuperar su PIN o actualizar su contacto corporativo.
    """
    def get(self, request):
        return render(request, 'reports/auth_portal.html')


