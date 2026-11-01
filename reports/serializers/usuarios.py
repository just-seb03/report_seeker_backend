"""
Serializadores para el modelo de Usuario y autenticación operativa.
"""

from typing import Optional
from rest_framework import serializers
from reports.models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer completo de Usuario para descarga de catálogos maestros (sync/pull).
    
    Incluye el PIN para permitir autenticación offline local en SQLite por parte de la app móvil.
    Construye la URL absoluta para la fotografía de perfil.
    """
    foto_perfil = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            'usuario_id',
            'nombre',
            'correo',
            'cargo',
            'foto_perfil',
            'pin',
            'habilitar_sumario',
            'estado',
            'updated_at',
        ]

    def get_foto_perfil(self, obj: Usuario) -> Optional[str]:
        """Resuelve la URL absoluta o relativa de la foto de perfil."""
        if obj.foto_perfil:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.foto_perfil.url)
            return obj.foto_perfil.url
        return None


class UsuarioPublicSerializer(serializers.ModelSerializer):
    """
    Serializer público de Usuario para respuestas de login y perfil activo en la interfaz.
    
    Excluye deliberadamente el campo 'pin' y metadatos de sincronización para mayor seguridad.
    """
    foto_perfil = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            'usuario_id',
            'nombre',
            'correo',
            'cargo',
            'habilitar_sumario',
            'foto_perfil',
        ]

    def get_foto_perfil(self, obj: Usuario) -> Optional[str]:
        """Resuelve la URL absoluta de la fotografía de perfil del usuario."""
        if obj.foto_perfil:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.foto_perfil.url)
            return obj.foto_perfil.url
        return None

