from django.contrib import admin
from django.utils.html import format_html
from .models import Usuario, Localizacion, Reporte, ReporteHistorial


class ReporteHistorialInline(admin.TabularInline):
    model = ReporteHistorial
    extra = 0
    can_delete = False
    readonly_fields = [
        'uuid',
        'usuario_nombre',
        'campo_modificado',
        'valor_anterior',
        'valor_nuevo',
        'fecha_cambio',
        'created_at',
    ]
    fields = [
        'campo_modificado',
        'valor_anterior',
        'valor_nuevo',
        'usuario_nombre',
        'fecha_cambio',
        'created_at',
    ]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = [
        'miniatura',
        'titulo',
        'prioridad_badge',
        'estado_badge',
        'usuario_nombre',
        'localizacion',
        'fecha_captura',
    ]
    list_filter = [
        'prioridad',
        'estado',
        'localizacion',
        'fecha_captura',
    ]
    search_fields = [
        'uuid',
        'titulo',
        'descripcion',
        'usuario_nombre',
        'ubicacion_texto',
    ]
    readonly_fields = [
        'uuid',
        'vista_previa_grande',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Identificación e Incidencia', {
            'fields': ('uuid', 'titulo', 'descripcion', 'prioridad', 'estado')
        }),
        ('Fotografía de Evidencia', {
            'fields': ('fotografia', 'vista_previa_grande')
        }),
        ('Origen y Ubicación', {
            'fields': ('usuario', 'usuario_nombre', 'usuario_cargo', 'localizacion', 'ubicacion_texto', 'fecha_captura')
        }),
        ('Auditoría del Sistema', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
    inlines = [ReporteHistorialInline]

    def miniatura(self, obj):
        if obj.fotografia:
            return format_html(
                '<img src="{}" style="width: 54px; height: 54px; object-fit: cover; border-radius: 6px; border: 1px solid #ccc;" />',
                obj.fotografia.url
            )
        return format_html('<span style="color: #999; font-style: italic;">Sin foto</span>')
    miniatura.short_description = "Foto"

    def vista_previa_grande(self, obj):
        if obj.fotografia:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="max-height: 320px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.15);" /></a>',
                obj.fotografia.url
            )
        return "No hay fotografía adjunta."
    vista_previa_grande.short_description = "Vista previa"

    def prioridad_badge(self, obj):
        colores = {
            'Alta': '#d32f2f',
            'Media': '#f57c00',
            'Baja': '#388e3c',
        }
        color = colores.get(obj.prioridad, '#555')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.prioridad
        )
    prioridad_badge.short_description = "Prioridad"

    def estado_badge(self, obj):
        colores = {
            'capturado': '#0288d1',
            'en_revision': '#7b1fa2',
            'resuelto': '#2e7d32',
        }
        color = colores.get(obj.estado, '#555')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 500; font-size: 11px;">{}</span>',
            color,
            obj.get_estado_display() if hasattr(obj, 'get_estado_display') else obj.estado
        )
    estado_badge.short_description = "Estado"


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = [
        'usuario_id',
        'avatar_preview',
        'nombre',
        'correo',
        'cargo',
        'habilitar_sumario',
        'estado_badge',
    ]
    list_filter = ['estado', 'habilitar_sumario', 'cargo']
    search_fields = ['usuario_id', 'nombre', 'correo', 'cargo']
    fields = [
        'usuario_id',
        'nombre',
        'correo',
        'cargo',
        'foto_perfil',
        'pin',
        'habilitar_sumario',
        'estado',
    ]

    def avatar_preview(self, obj):
        if obj.foto_perfil:
            return format_html(
                '<img src="{}" style="width: 36px; height: 36px; object-fit: cover; border-radius: 50%;" />',
                obj.foto_perfil.url
            )
        return format_html('<span style="color: #aaa;">-</span>')
    avatar_preview.short_description = "Avatar"

    def estado_badge(self, obj):
        color = '#2e7d32' if obj.estado == 'activo' else '#d32f2f'
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color,
            obj.estado.capitalize()
        )
    estado_badge.short_description = "Estado"


@admin.register(Localizacion)
class LocalizacionAdmin(admin.ModelAdmin):
    list_display = ['id', 'nombre', 'activo', 'updated_at']
    list_filter = ['activo']
    search_fields = ['nombre']


@admin.register(ReporteHistorial)
class ReporteHistorialAdmin(admin.ModelAdmin):
    list_display = [
        'uuid',
        'reporte',
        'usuario_nombre',
        'campo_modificado',
        'valor_anterior',
        'valor_nuevo',
        'fecha_cambio',
        'created_at',
    ]
    list_filter = ['campo_modificado', 'fecha_cambio']
    search_fields = ['uuid', 'reporte__uuid', 'usuario_nombre', 'valor_nuevo']
    readonly_fields = [f.name for f in ReporteHistorial._meta.fields]

    def has_add_permission(self, request):
        return False
