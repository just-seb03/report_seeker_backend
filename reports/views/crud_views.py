"""
Controladores CRUD basados en ViewSets para la API navegable de Django REST Framework.

Este módulo expone los recursos principales del sistema mediante `ModelViewSet`:
- `ReporteViewSet`: Gestiona las operaciones de listado, creación, detalle, actualización
  y eliminación de incidencias.
- `LocalizacionViewSet`: Gestiona el catálogo de sectores físicos y zonas de trabajo.

Dónde se utiliza:
- En la interfaz web navegable de DRF (`/api/v1/reportes/` y `/api/v1/localizaciones/`).
- En integraciones con paneles de visualización y herramientas administrativas externas
  que consumen directamente operaciones REST estándar.
- Registrado de forma centralizada en el `DefaultRouter` de `reports/urls.py`.
"""

from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from reports.models import Reporte, Localizacion
from reports.pagination import StandardResultsPagination
from reports.serializers import ReporteSerializer, LocalizacionSerializer


class ReporteViewSet(viewsets.ModelViewSet):
    """
    Controlador REST integral para el modelo Reporte.
    
    Provee las siguientes acciones automáticas:
    - `GET /api/v1/reportes/`: Lista todos los reportes ordenados cronológicamente y
      muestra el formulario de creación en la interfaz web de DRF.
    - `POST /api/v1/reportes/`: Crea un nuevo reporte validando datos obligatorios.
    - `GET /api/v1/reportes/<pk>/`: Consulta la información detallada de un reporte específico.
    - `PUT /api/v1/reportes/<pk>/` / `PATCH /api/v1/reportes/<pk>/`: Actualiza datos de un reporte existente.
    - `DELETE /api/v1/reportes/<pk>/`: Elimina un reporte del sistema.
    
    Dónde se utiliza:
    - En la interfaz interactiva navegable de DRF.
    - Como interfaz de integración para reportes individuales sin pasar por sincronización por lotes.
    """
    queryset = Reporte.objects.all().order_by('-fecha_captura')
    serializer_class = ReporteSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination
    search_fields = ['titulo', 'descripcion', 'usuario_nombre', 'ubicacion_texto']


class LocalizacionViewSet(viewsets.ModelViewSet):
    """
    Controlador REST integral para el catálogo maestro de Localizaciones.
    
    Provee las siguientes acciones automáticas:
    - `GET /api/v1/localizaciones/`: Lista todos los sectores registrados y el formulario para añadir nuevos.
    - `POST /api/v1/localizaciones/`: Registra un nuevo sector o área física de trabajo.
    - `GET /api/v1/localizaciones/<pk>/`: Consulta el detalle de un sector específico.
    - `PUT /api/v1/localizaciones/<pk>/`: Modifica el nombre o estado activo de un sector.
    - `DELETE /api/v1/localizaciones/<pk>/`: Elimina un sector del catálogo.
    
    Dónde se utiliza:
    - En la gestión administrativa de sectores mediante la API navegable de DRF.
    """
    queryset = Localizacion.objects.all().order_by('id')
    serializer_class = LocalizacionSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination
