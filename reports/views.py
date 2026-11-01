from django.contrib.auth.models import User
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

from .models import Usuario, Localizacion, Reporte, ReporteHistorial
from .serializers import (
    UsuarioSerializer,
    UsuarioPublicSerializer,
    ReportePullSerializer,
    SyncPushPayloadSerializer,
    VerifyWorkerSerializer,
    PinRecoverySerializer,
    ChangeEmailSerializer,
)


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


class AuthPortalWebView(View):
    """
    GET /auth/portal/
    Renderiza la interfaz web de autoservicio para recuperación de PIN y cambio de correo.
    """
    def get(self, request):
        return render(request, 'reports/auth_portal.html')

