"""
Controladores del Sistema y Monitoreo de Estado (Health Check).

Este módulo provee endpoints para supervisión operacional y diagnóstico de infraestructura:
- `HealthCheckView`: Comprueba la conectividad hacia la base de datos y reporta el estado
  operativo del nodo sin comprometer información sensible.

Dónde se utiliza:
- En balanceadores de carga, monitores de disponibilidad (uptime monitors) y proxies.
- En la verificación de red que realiza el cliente móvil antes de iniciar ciclos de sincronización pesados.
"""

from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """
    GET /api/v1/health/
    
    Verifica la salud operativa del backend:
    - Estado de la base de datos (consulta trivial de comprobación de conexión).
    - Estado de la capa de transporte (detección de HTTPS / SSL).
    - Marca de tiempo del servidor para sincronización horaria.
    
    Dónde se utiliza:
    - En sondas de salud (health probes) de contenedores, servidores y balanceadores.
    - En el diagnóstico preventivo de conectividad desde la aplicación móvil.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        db_ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
        except Exception:
            db_ok = False

        es_seguro = request.is_secure()

        datos_estado = {
            'status': 'healthy' if db_ok else 'degraded',
            'database': 'connected' if db_ok else 'unreachable',
            'is_https': es_seguro,
            'server_timestamp': timezone.now().isoformat(),
        }

        codigo_http = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(datos_estado, status=codigo_http)


