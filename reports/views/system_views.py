"""
Controladores del Sistema y Verificación de Estado (Health Check).

Este módulo provee endpoints para monitoreo operacional y verificación de conectividad
por parte de clientes móviles y herramientas de infraestructura:
- `HealthCheckView`: Comprueba conectividad a la base de datos SQLite y estado de seguridad del nodo.
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
    - Estado de la base de datos (consulta ping trivial).
    - Estado de transporte (HTTP vs HTTPS detectado).
    - Marca de tiempo del servidor.
    
    Seguridad: No expone rutas, variables de entorno ni detalles internos del sistema.
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

