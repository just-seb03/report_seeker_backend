"""
Serializadores para el modelo de Usuario y autenticación operativa.

Este módulo provee las clases serializadoras para la representación del personal operativo:
- `UsuarioSerializer`: Serializador completo que incluye el PIN numérico para descarga de catálogos maestros.
- `UsuarioPublicSerializer`: Serializador seguro que expone únicamente datos públicos (sin PIN).

Dónde se utiliza:
- `UsuarioSerializer`: Utilizado en `SyncPullView` (`/api/v1/sync/pull/`) para que la app móvil almacene
  la nómina de operarios en su SQLite local y permita login offline sin red.
- `UsuarioPublicSerializer`: Utilizado en `LoginView` (`/api/v1/auth/login/`) para retornar el perfil del operario autenticado.
"""

from typing import Optional
from rest_framework import serializers
from reports.models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer de Usuario para descarga de catálogos maestros (`sync/pull`).
    
    Incluye el PIN numérico para permitir la autenticación offline local en SQLite por parte de la app móvil.
    Construye la URL absoluta para la fotografía de perfil.
    
    Dónde se utiliza:
    - En `SyncPullView` (`/api/v1/sync/pull/`), consumido por `SyncService.ts`.
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
    
    Excluye deliberadamente el campo 'pin' y metadatos internos de sincronización por seguridad.
    
    Dónde se utiliza:
    - En `LoginView` (`/api/v1/auth/login/`) al responder con las credenciales validadas.
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


