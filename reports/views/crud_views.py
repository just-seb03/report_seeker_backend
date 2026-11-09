"""
Controladores CRUD y Vistas Genéricas basadas en ModelViewSet de Django REST Framework.

Este módulo implementa los controladores REST navegables para la administración y consulta
de las entidades primarias del sistema (Reportes, Localizaciones y Usuarios).

ModelViewSets provistos:
- `ReporteViewSet`: Operaciones CRUD completas sobre incidencias mineras.
  Soporta paginación estándar, búsqueda multi-campo, filtros por estado/prioridad y ordenamiento.
  Aplica permisos IsAuthenticatedOrReadOnly e IsAuthorOrReadOnly.
- `LocalizacionViewSet`: Operaciones CRUD sobre áreas físicas y sectores de faena.
  Aplica paginación estándar, búsqueda, ordenamiento y permiso IsAuthenticatedOrReadOnly.
- `UsuarioViewSet`: Consulta de sólo lectura (ReadOnlyModelViewSet) para operarios y supervisores,
  sin exponer credenciales ni PINs.

Dónde se utiliza:
- Conectados al `DefaultRouter` en `reports/urls.py` para la API REST navegable (`/api/v1/`).
- Consumidos por la interfaz navegable de DRF y herramientas de supervisión externa.
"""

from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from reports.models import Reporte, Localizacion, Usuario
from reports.pagination import StandardResultsPagination
from reports.permissions import IsAuthorOrReadOnly
from reports.serializers import (
    ReporteSerializer,
    LocalizacionSerializer,
    UsuarioPublicSerializer,
)


class ReporteViewSet(viewsets.ModelViewSet):
    """
    Controlador RESTful para la entidad central Reporte.

    Provee endpoints para listar, crear, consultar, actualizar y eliminar incidencias
    registradas en faena minera.

    Características implementadas:
    - Paginación estándar (10 por página, configurable hasta 100 con ?page_size=).
    - Búsqueda textual multi-campo en título, descripción, usuario_nombre y ubicación (?search=).
    - Filtrado exacto insensible a mayúsculas por ?prioridad= y ?estado=.
    - Ordenamiento por fecha de captura, prioridad, estado y fecha de creación (?ordering=).
    - Autorización granular: lectura pública, creación autenticada, y modificación/eliminación
      restringida al autor del reporte o administradores (is_staff).

    Dónde se utiliza:
    - En la interfaz interactiva navegable de DRF (`/api/v1/reportes/`).
    - Como interfaz de integración para reportes individuales sin pasar por sincronización por lotes.
    """
    queryset = Reporte.objects.select_related('localizacion', 'usuario').all().order_by('-fecha_captura')
    serializer_class = ReporteSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    pagination_class = StandardResultsPagination
    search_fields = ['titulo', 'descripcion', 'usuario_nombre', 'ubicacion_texto']
    ordering_fields = ['fecha_captura', 'prioridad', 'estado', 'created_at']
    ordering = ['-fecha_captura']

    def get_queryset(self):
        queryset = super().get_queryset()
        if not getattr(self, 'request', None):
            return queryset

        filters = {}

        prioridad = self.request.query_params.get('prioridad')
        if prioridad:
            filters['prioridad__iexact'] = prioridad.strip()

        estado = self.request.query_params.get('estado')
        if estado:
            filters['estado__iexact'] = estado.strip()

        return queryset.filter(**filters)

    def perform_create(self, serializer):
        """
        Asocia automáticamente el usuario autenticado como autor del reporte
        al momento de registrarlo desde la API navegable.
        """
        usuario_op = None
        if self.request.user and self.request.user.is_authenticated:
            if str(self.request.user.username).isdigit():
                usuario_op = Usuario.objects.filter(usuario_id=int(self.request.user.username)).first()

        if usuario_op:
            serializer.save(
                usuario=usuario_op,
                usuario_nombre=usuario_op.nombre,
                usuario_cargo=usuario_op.cargo
            )
        else:
            serializer.save()


class LocalizacionViewSet(viewsets.ModelViewSet):
    """
    Controlador RESTful para el catálogo maestro de áreas físicas y sectores de faena minera.

    Provee endpoints para listar y administrar sectores como túneles, frentes y plantas.

    Características implementadas:
    - Paginación estándar (10 por página).
    - Búsqueda por nombre (?search=).
    - Ordenamiento por id, nombre y activo (?ordering=).
    - Permisos: lectura pública, modificación restringida a usuarios autenticados.

    Dónde se utiliza:
    - En la interfaz interactiva navegable de DRF (`/api/v1/localizaciones/`).
    - Como catálogo maestro de referencia para la creación y clasificación de reportes.
    """
    queryset = Localizacion.objects.all().order_by('id')
    serializer_class = LocalizacionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsPagination
    search_fields = ['nombre']
    ordering_fields = ['id', 'nombre', 'activo']
    ordering = ['id']


class UsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    """Controlador de solo lectura para consultar usuarios sin exponer el PIN."""

    queryset = Usuario.objects.all().order_by('usuario_id')
    serializer_class = UsuarioPublicSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination
    search_fields = ['nombre', 'correo', 'cargo']
    ordering_fields = ['usuario_id', 'nombre', 'cargo']
    ordering = ['usuario_id']
