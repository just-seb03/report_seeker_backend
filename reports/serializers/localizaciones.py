"""
Serializadores para el catálogo de Localizaciones y sectores de faena.
"""

from rest_framework import serializers
from reports.models import Localizacion


class LocalizacionSerializer(serializers.ModelSerializer):
    """
    Serializer de Localizacion para catálogos maestros y sincronización delta.
    """
    class Meta:
        model = Localizacion
        fields = ['id', 'nombre', 'activo', 'updated_at']

