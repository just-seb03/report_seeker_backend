"""
Permisos personalizados para la API de Report Seeker.

Define reglas de autorización basadas en objetos y roles:
- `IsAuthorOrReadOnly`: Permite lectura a usuarios autenticados, pero restringe
  la modificación o eliminación únicamente al autor del reporte o administradores (staff).
"""

from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Permiso a nivel de objeto que permite métodos de lectura (GET, HEAD, OPTIONS)
    a cualquier cliente con acceso, pero solo permite escritura (PUT, PATCH, DELETE)
    al usuario que creó el reporte o a supervisores con rol staff.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        # Métodos seguros de lectura (GET, HEAD, OPTIONS) son siempre permitidos
        if request.method in permissions.SAFE_METHODS:
            return True

        # Si el usuario es supervisor/administrador de faena (staff), se permite modificar
        if request.user and request.user.is_staff:
            return True

        # Si el objeto tiene un usuario asignado, verificar coincidencia con el usuario autenticado
        if hasattr(obj, 'usuario') and obj.usuario:
            return str(obj.usuario.usuario_id) == str(request.user.username)

        return False

