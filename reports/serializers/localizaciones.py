"""
Serializadores para el catálogo de Localizaciones y sectores de faena.

Este módulo define la serialización del catálogo maestro de áreas de trabajo:
- `LocalizacionSerializer`: Mapea los sectores, su estado activo y fecha de actualización.

Dónde se utiliza:
- En `SyncPullView` (`/api/v1/sync/pull/`) para alimentar el catálogo offline de la app móvil.
- En `LocalizacionViewSet` (`/api/v1/localizaciones/`) para la API navegable y administración REST.
"""

from rest_framework import serializers
from reports.models import Localizacion


class LocalizacionSerializer(serializers.ModelSerializer):
    """
    Serializer de Localizacion para catálogos maestros y operaciones CRUD.
    
    Dónde se utiliza:
    - En `LocalizacionViewSet` y en la sincronización delta descendente hacia la app móvil.
    """
    class Meta:
        model = Localizacion
        fields = ['id', 'nombre', 'activo', 'updated_at']


