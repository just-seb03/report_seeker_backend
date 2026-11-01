"""
Controladores de Sincronización de Datos Offline (Push & Pull).

Este módulo expone los endpoints que utiliza el motor de sincronización del cliente móvil:
- `SyncPushView`: Recepción en lote de reportes e historiales generados offline en faena.
- `SyncPullView`: Descarga delta de catálogos y reportes modificados en el servidor.
"""

from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.serializers import (
    SyncPushPayloadSerializer,
    ReportePullSerializer,
    UsuarioSerializer,
)
from reports.services import (
    procesar_push_sincronizacion,
    obtener_conjuntos_pull,
)


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

        # Delegar la sincronización atómica e idempotente al servicio de dominio
        resultado = procesar_push_sincronizacion(reportes_data, historial_data)

        return Response(resultado, status=status.HTTP_200_OK)


class SyncPullView(APIView):
    """
    GET /api/v1/sync/pull/?since=<ISO_TIMESTAMP>
    
    Envía al dispositivo móvil las actualizaciones de catálogos y reportes ocurridas en el servidor
    a partir del timestamp `since` proporcionado.
    
    Especificación: BACKEND_SPEC.md § 4.3
    """
    permission_classes = [AllowAny]

    def get(self, request):
        since_param = request.query_params.get('since')
        since_dt = None
        if since_param:
            since_dt = parse_datetime(since_param)

        locs_qs, users_qs, reportes_qs, timestamp_servidor = obtener_conjuntos_pull(since_dt)

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
            'server_timestamp': timestamp_servidor.isoformat(),
            'catalogos': catalogos,
            'reportes': reportes_data,
        }, status=status.HTTP_200_OK)

