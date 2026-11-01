import datetime
import logging
import secrets
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.generic import View
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Usuario, Localizacion, Reporte, ReporteHistorial, CodigoVerificacion
from .serializers import (
    UsuarioSerializer,
    UsuarioPublicSerializer,
    ReportePullSerializer,
    SyncPushPayloadSerializer,
    VerifyWorkerSerializer,
    PinRecoverySerializer,
    ChangeEmailSerializer,
    RequestPinResetSerializer,
    VerifyPinResetSerializer,
)

logger = logging.getLogger(__name__)


def enmascarar_correo(correo: str) -> str:
    """Enmascara un correo para visualización segura: sebastian@minera.cl -> s***n@minera.cl"""
    if '@' not in correo:
        return correo
    user, domain = correo.split('@', 1)
    if len(user) <= 2:
        masked_user = user[0] + '*'
    else:
        masked_user = user[0] + '***' + user[-1]
    return f"{masked_user}@{domain}"


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Valida credenciales de faena (usuario_id + pin) y retorna token de sesión y perfil de usuario.
    Especificación: BACKEND_SPEC.md § 4.1
    """
    permission_classes = [AllowAny]

    def post(self, request):
        usuario_id = request.data.get('usuario_id')
        pin = request.data.get('pin')

        if not usuario_id or not pin:
            return Response(
                {'error': 'Se requieren usuario_id y pin.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            usuario = Usuario.objects.get(usuario_id=usuario_id, estado='activo')
        except Usuario.DoesNotExist:
            return Response(
                {'error': 'Credenciales inválidas o usuario inactivo.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not usuario.check_pin(str(pin)):
            return Response(
                {'error': 'Credenciales inválidas o usuario inactivo.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

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


class SyncPushView(APIView):
    """
    POST /api/v1/sync/push/
    Procesa en lote y de forma idempotente reportes y eventos de historial enviados por el móvil.
    Especificación: BACKEND_SPEC.md § 4.2
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SyncPushPayloadSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        reportes_data = data.get('reportes', [])
        historial_data = data.get('historial', [])

        synced_reports = []
        synced_historial = []

        with transaction.atomic():
            # 1. Sincronizar reportes
            for rep in reportes_data:
                rep_uuid = rep['uuid']
                local_id = rep.get('local_id')

                # Resolver relaciones foráneas lógicas
                usuario = None
                if rep.get('usuario_id'):
                    usuario = Usuario.objects.filter(usuario_id=rep['usuario_id']).first()

                localizacion = None
                if rep.get('ubicacion_id'):
                    localizacion = Localizacion.objects.filter(id=rep['ubicacion_id']).first()
                elif rep.get('ubicacion'):
                    localizacion = Localizacion.objects.filter(nombre=rep['ubicacion']).first()

                defaults = {
                    'titulo': rep['titulo'],
                    'descripcion': rep.get('descripcion') or '',
                    'fecha_captura': rep['fecha_captura'],
                    'usuario': usuario,
                    'usuario_nombre': rep.get('usuario_nombre') or (usuario.nombre if usuario else ''),
                    'usuario_cargo': rep.get('usuario_cargo') or (usuario.cargo if usuario else ''),
                    'localizacion': localizacion,
                    'ubicacion_texto': rep.get('ubicacion') or (localizacion.nombre if localizacion else ''),
                    'prioridad': rep.get('prioridad', 'Media'),
                    'estado': rep.get('estado', 'capturado'),
                }

                # Operación idempotente: si el reporte ya existe por UUID, actualiza
                reporte_obj, created = Reporte.objects.update_or_create(
                    uuid=rep_uuid,
                    defaults=defaults
                )

                # Si viene una fotografía decodificada por Base64ImageField, asignarla
                foto_file = rep.get('fotografia_base64')
                if foto_file:
                    reporte_obj.fotografia = foto_file
                    reporte_obj.save(update_fields=['fotografia'])

                synced_reports.append({
                    'local_id': local_id,
                    'uuid': str(rep_uuid),
                    'status': 'sincronizado'
                })

            # 2. Sincronizar auditoría / historial
            for hist in historial_data:
                hist_uuid = hist['uuid']
                local_id = hist.get('local_id')
                rep_uuid = hist['reporte_uuid']

                reporte_obj = Reporte.objects.filter(uuid=rep_uuid).first()
                if not reporte_obj:
                    # Si el reporte no fue encontrado (caso anómalo), continuar sin quebrar el lote
                    continue

                usuario = None
                if hist.get('usuario_id'):
                    usuario = Usuario.objects.filter(usuario_id=hist['usuario_id']).first()

                hist_defaults = {
                    'reporte': reporte_obj,
                    'usuario': usuario,
                    'usuario_nombre': hist.get('usuario_nombre') or (usuario.nombre if usuario else 'Usuario'),
                    'campo_modificado': hist['campo_modificado'],
                    'valor_anterior': hist.get('valor_anterior'),
                    'valor_nuevo': hist.get('valor_nuevo') or '',
                    'fecha_cambio': hist['fecha_cambio'],
                }

                # Operación idempotente para entradas de historial
                ReporteHistorial.objects.update_or_create(
                    uuid=hist_uuid,
                    defaults=hist_defaults
                )

                synced_historial.append({
                    'local_id': local_id,
                    'uuid': str(hist_uuid),
                    'status': 'sincronizado'
                })

        return Response({
            'status': 'success',
            'synced_reports': synced_reports,
            'synced_historial': synced_historial,
        }, status=status.HTTP_200_OK)


class SyncPullView(APIView):
    """
    GET /api/v1/sync/pull/?since=<ISO_TIMESTAMP>
    Envía al dispositivo móvil las actualizaciones de catálogos y reportes ocurridas en el backend.
    Especificación: BACKEND_SPEC.md § 4.3
    """
    permission_classes = [AllowAny]

    def get(self, request):
        since_param = request.query_params.get('since')
        since_dt = None
        if since_param:
            since_dt = parse_datetime(since_param)

        now = timezone.now()

        # Filtrado delta si se especifica timestamp 'since'
        if since_dt:
            locs_qs = Localizacion.objects.filter(updated_at__gte=since_dt, activo=True)
            users_qs = Usuario.objects.filter(updated_at__gte=since_dt)
            reportes_qs = Reporte.objects.filter(updated_at__gte=since_dt).order_by('-fecha_captura')
        else:
            locs_qs = Localizacion.objects.filter(activo=True)
            users_qs = Usuario.objects.filter(estado='activo')
            reportes_qs = Reporte.objects.all().order_by('-fecha_captura')[:100]

        catalogos = {
            'localizaciones': [
                {'id': loc.id, 'nombre': loc.nombre}
                for loc in locs_qs
            ],
            'usuarios': UsuarioSerializer(users_qs, many=True, context={'request': request}).data,
        }

        reportes_data = ReportePullSerializer(
            reportes_qs,
            many=True,
            context={'request': request}
        ).data

        return Response({
            'server_timestamp': now.isoformat(),
            'catalogos': catalogos,
            'reportes': reportes_data,
        }, status=status.HTTP_200_OK)


class VerifyWorkerView(APIView):
    """
    POST /api/v1/auth/verify-worker/
    Valida si el ID y correo corresponden a un usuario activo.
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
    Restablece el PIN del usuario activo.
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
    Actualiza el correo corporativo del usuario tras validar su PIN.
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
    para permitir la recuperación de su PIN de acceso.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RequestPinResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data['usuario']
        correo = usuario.correo

        # 1. Invalidar códigos previos no utilizados de este usuario
        usuario.codigos_verificacion.filter(utilizado=False).update(utilizado=True)

        # 2. Generar código numérico criptográficamente seguro de 6 dígitos (100000 - 999999)
        codigo = f"{secrets.randbelow(900000) + 100000}"
        expira_en = timezone.now() + datetime.timedelta(minutes=15)

        # 3. Persistir código en base de datos
        CodigoVerificacion.objects.create(
            usuario=usuario,
            correo=correo,
            codigo=codigo,
            expira_en=expira_en,
        )

        # 4. Despachar correo electrónico
        asunto = f"Report Seeker - Código de Seguridad: {codigo}"
        mensaje_texto = (
            f"Hola, {usuario.nombre}:\n\n"
            f"Has solicitado restablecer tu PIN de acceso para Report Seeker en Faena Minera.\n\n"
            f"Tu código de seguridad de 6 dígitos es:\n"
            f"--> {codigo} <--\n\n"
            f"Este código es válido por 15 minutos.\n"
            f"Si no realizaste esta solicitud, puedes ignorar este mensaje.\n"
        )

        mensaje_html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0A1118; color: #F8FAFC;">
          <div style="max-width: 500px; margin: 0 auto; background-color: #101E2E; border: 1px solid #22384F; border-radius: 14px; padding: 28px; box-shadow: 0 8px 24px rgba(0,0,0,0.5);">
            <div style="text-align: center; margin-bottom: 24px;">
              <span style="background: rgba(229,169,60,0.15); border: 1px solid rgba(229,169,60,0.3); color: #E5A93C; font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; padding: 4px 10px; border-radius: 20px;">
                Report Seeker &bull; Faena Minera
              </span>
              <h2 style="color: #F8FAFC; margin: 14px 0 4px 0; font-size: 20px;">Recuperación de PIN de Acceso</h2>
              <p style="color: #94A3B8; font-size: 13px; margin: 0;">Servidor Central de Operaciones</p>
            </div>
            
            <p style="font-size: 14px; line-height: 1.5; color: #E2E8F0;">
              Hola, <strong>{usuario.nombre}</strong> ({usuario.cargo}):
            </p>
            <p style="font-size: 14px; line-height: 1.5; color: #94A3B8;">
              Ingresa el siguiente código de 6 dígitos en la aplicación móvil o en el portal web para restablecer tu clave de 4 dígitos:
            </p>

            <div style="background-color: #18283D; border: 2px dashed #3B82F6; border-radius: 10px; padding: 20px; text-align: center; margin: 24px 0;">
              <span style="font-size: 34px; font-weight: 800; letter-spacing: 10px; color: #3B82F6; font-family: monospace;">{codigo}</span>
            </div>

            <p style="font-size: 13px; color: #94A3B8; line-height: 1.4;">
              ⏱ <strong>Válido por 15 minutos</strong> &bull; Uso único.<br>
              🔒 Por seguridad, nunca compartas este código con terceros.
            </p>
            
            <hr style="border: none; border-top: 1px solid #22384F; margin: 24px 0;">
            
            <p style="font-size: 11px; color: #64748B; text-align: center; margin: 0;">
              Si tú no solicitaste este código, tu cuenta permanece segura y puedes desestimar este correo.
            </p>
          </div>
        </body>
        </html>
        """

        try:
            send_mail(
                subject=asunto,
                message=mensaje_texto,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'Report Seeker <noreply@minera.cl>'),
                recipient_list=[correo],
                html_message=mensaje_html,
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Fallo al enviar correo OTP a {correo}: {e}")
            # Si falla la conexión SMTP (ej. sin salida a internet en la laptop)
            return Response({
                'status': 'error',
                'message': 'No se pudo conectar con el servidor de correo. Verifica tu conexión a internet.',
                'error_detail': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            'status': 'success',
            'message': 'Código de verificación enviado exitosamente a tu correo corporativo.',
            'usuario_id': usuario.usuario_id,
            'correo_enmascarado': enmascarar_correo(correo),
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

        # 1. Marcar el código OTP como utilizado
        otp_obj.utilizado = True
        otp_obj.save(update_fields=['utilizado'])

        # 2. Actualizar PIN del usuario en texto plano para compatibilidad offline
        usuario.set_pin(nuevo_pin)
        usuario.save(update_fields=['pin', 'updated_at'])

        # 3. Sincronizar contraseña de Django User (para tokens DRF)
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


class AuthPortalWebView(View):
    """
    GET /auth/portal/
    Renderiza la interfaz web de autoservicio para recuperación de PIN y cambio de correo.
    """
    def get(self, request):
        return render(request, 'reports/auth_portal.html')

