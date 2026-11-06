"""
Controladores de Sincronización de Datos Offline (Push & Pull).

Este módulo gestiona la sincronización bidireccional entre la base de datos central
y los dispositivos móviles que operan sin conexión en terreno:
- `SyncPushView`: Recepción en lote de reportes e historiales de cambios generados offline.
- `SyncPullView`: Descarga incremental (delta) de catálogos y reportes modificados en el servidor.

Dónde se utiliza:
- En la aplicación móvil: `SyncService.ts` invoca periódicamente `SyncPushView` para subir
  la cola de reportes pendientes y `SyncPullView` para actualizar la base de datos local SQLite.
- En las pruebas de sincronización: `reports/tests/test_sync.py`.
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
    
    Procesa de manera atómica e idempotente los lotes de reportes e historiales de auditoría
    enviados por los dispositivos móviles.
    
    Mecanismos de protección:
    - Limitación de tasa (`throttle_scope = 'sync_push'`): Máximo 60 peticiones por minuto
      para prevenir sobrecarga de disco y saturación de memoria durante subidas masivas.
    - Idempotencia por UUID: Previene la duplicación de reportes ante reintentos de red.
    
    Dónde se utiliza:
    - En `SyncService.ts` de la aplicación móvil cuando el dispositivo recupera conectividad
      y vacía su cola local de registros pendientes de subida.
    """
    permission_classes = [AllowAny]
    throttle_scope = 'sync_push'

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
    
    Envía al dispositivo móvil únicamente los registros que hayan sufrido cambios en el servidor
    a partir de la fecha y hora (`since`) provista por el cliente móvil.
    
    Mecanismos de protección:
    - Limitación de tasa (`throttle_scope = 'sync_pull'`): Restringe descargas excesivas
      o continuas por parte de clientes automatizados.
    
    Dónde se utiliza:
    - En el arranque de la aplicación móvil y en cada ciclo de sincronización de `SyncService.ts`
      para actualizar los catálogos maestros (usuarios, localizaciones) y reportes recientes en SQLite local.
    """
    permission_classes = [AllowAny]
    throttle_scope = 'sync_pull'

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


