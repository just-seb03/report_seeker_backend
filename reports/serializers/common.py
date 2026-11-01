"""
Serializadores y campos comunes reutilizables.
"""

import base64
import uuid
from typing import Optional
from django.core.files.base import ContentFile
from rest_framework import serializers


class Base64ImageField(serializers.Field):
    """
    Campo personalizado de DRF para decodificar cadenas de imagen Base64.
    
    Admite esquemas de datos Data URI (ej. 'data:image/webp;base64,...', 'data:image/jpeg;base64,...')
    o strings Base64 planos, transformándolos en un `ContentFile` almacenable en `MEDIA_ROOT`.
    En la representación de salida, genera la URL absoluta para el cliente móvil.
    """

    def to_internal_value(self, data) -> Optional[ContentFile]:
        """
        Convierte una cadena Base64 recibida en un archivo binario `ContentFile`.

        Args:
            data: Cadena Base64 o Data URI de la imagen.

        Returns:
            Optional[ContentFile]: Archivo listo para asignar al ImageField del modelo.

        Raises:
            serializers.ValidationError: Si el formato no es string o los bytes están corruptos.
        """
        if not data:
            return None

        if not isinstance(data, str):
            raise serializers.ValidationError("El formato de la imagen debe ser un string Base64.")

        ext = 'webp'
        if 'base64,' in data:
            header, base64_data = data.split('base64,', 1)
            if 'image/webp' in header:
                ext = 'webp'
            elif 'image/png' in header:
                ext = 'png'
            elif 'image/jpeg' in header or 'image/jpg' in header:
                ext = 'jpg'
        else:
            base64_data = data

        try:
            decoded_bytes = base64.b64decode(base64_data)
        except Exception:
            raise serializers.ValidationError("Cadena Base64 inválida o corrupta.")

        filename = f"foto_{uuid.uuid4().hex[:10]}.{ext}"
        return ContentFile(decoded_bytes, name=filename)

    def to_representation(self, value) -> Optional[str]:
        """
        Convierte el objeto File/FieldFile en una URL pública absoluta o relativa.
        """
        if not value:
            return None
        request = self.context.get('request')
        if request and hasattr(value, 'url'):
            return request.build_absolute_uri(value.url)
        return getattr(value, 'url', None)

