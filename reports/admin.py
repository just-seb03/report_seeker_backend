from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Usuario, Localizacion, Reporte, ReporteHistorial

# Configuración de Branding del Panel Central de Faena
admin.site.site_header = "Report Seeker — Servidor Central"
admin.site.site_title = "Report Seeker"
admin.site.index_title = "Panel de Auditoría, Control y Gestión de Faena"


class ReporteHistorialInline(admin.TabularInline):
    """
    Despliegue tabular de la bitácora de auditoría dentro de la ficha del reporte.
    Inmutable: solo lectura, sin opción de agregar o eliminar eventos históricos.
    """
    model = ReporteHistorial
    extra = 0
    can_delete = False
    readonly_fields = [
        'uuid',
        'campo_modificado',
        'valor_anterior_formateado',
        'valor_nuevo_formateado',
        'usuario_nombre',
        'fecha_cambio',
        'created_at',
    ]
    fields = [
        'campo_modificado',
        'valor_anterior_formateado',
        'valor_nuevo_formateado',
        'usuario_nombre',
        'fecha_cambio',
        'created_at',
    ]

    def has_add_permission(self, request, obj=None):
        return False

    def valor_anterior_formateado(self, obj):
        if not obj.valor_anterior:
            return mark_safe('<span style="color: #888; font-style: italic;">(Inicial)</span>')
        return obj.valor_anterior
    valor_anterior_formateado.short_description = "Valor Anterior"

    def valor_nuevo_formateado(self, obj):
        return format_html('<strong>{}</strong>', obj.valor_nuevo)
    valor_nuevo_formateado.short_description = "Valor Nuevo"


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    """
    Panel administrativo de incidencias para supervisores y prevencionistas.
    """
    list_display = [
        'miniatura',
        'titulo',
        'prioridad_badge',
        'estado_badge',
        'usuario_nombre',
        'localizacion',
        'fecha_captura',
    ]
    list_display_links = ['miniatura', 'titulo']
    list_filter = [
        'prioridad',
        'estado',
        'localizacion',
        ('fecha_captura', admin.DateFieldListFilter),
        'created_at',
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
    date_hierarchy = 'fecha_captura'
    list_per_page = 25
    actions = ['marcar_en_revision', 'marcar_resuelto']

    fieldsets = (
        ('Identificación e Incidencia', {
            'fields': ('uuid', 'titulo', 'descripcion', 'prioridad', 'estado')
        }),
        ('Fotografía de Evidencia', {
            'fields': ('fotografia', 'vista_previa_grande')
        }),
        ('Origen y Ubicación en Faena', {
            'fields': (
                'usuario',
                'usuario_nombre',
                'usuario_cargo',
                'localizacion',
                'ubicacion_texto',
                'fecha_captura'
            )
        }),
        ('Auditoría del Sistema', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
    inlines = [ReporteHistorialInline]

    # --- Acciones Rápidas en Lote ---
    @admin.action(description="Marcar reportes seleccionados como 'En Revisión'")
    def marcar_en_revision(self, request, queryset):
        actualizados = queryset.update(estado='en_revision')
        if request:
            self.message_user(request, f"{actualizados} reporte(s) cambiaron a estado 'En Revisión'.")

    @admin.action(description="Marcar reportes seleccionados como 'Resuelto'")
    def marcar_resuelto(self, request, queryset):
        actualizados = queryset.update(estado='resuelto')
        if request:
            self.message_user(request, f"{actualizados} reporte(s) fueron marcados como 'Resuelto'.")

    # --- Renderizado de Miniaturas y Badges ---
    def miniatura(self, obj):
        if obj.fotografia:
            return format_html(
                '<a href="{0}" target="_blank" title="Ver foto completa">'
                '<img src="{0}" style="width: 52px; height: 52px; object-fit: cover; border-radius: 6px; border: 1px solid #ddd; box-shadow: 0 1px 3px rgba(0,0,0,0.1);" />'
                '</a>',
                obj.fotografia.url
            )
        return mark_safe(
            '<span style="display: inline-block; width: 52px; height: 52px; line-height: 52px; text-align: center; '
            'background: #f0f0f0; color: #999; border-radius: 6px; font-size: 10px; font-weight: bold;">SIN FOTO</span>'
        )
    miniatura.short_description = "Foto"

    def vista_previa_grande(self, obj):
        if obj.fotografia:
            return format_html(
                '<div style="margin-top: 5px;">'
                '<a href="{0}" target="_blank">'
                '<img src="{0}" style="max-height: 380px; max-width: 100%; border-radius: 8px; box-shadow: 0 3px 8px rgba(0,0,0,0.2); border: 1px solid #ccc;" />'
                '</a>'
                '<p style="font-size: 11px; color: #666; margin-top: 4px;">(Haz clic en la imagen para abrirla en resolución original)</p>'
                '</div>',
                obj.fotografia.url
            )
        return mark_safe('<p style="color: #888; font-style: italic;">No se adjuntó fotografía en este reporte.</p>')
    vista_previa_grande.short_description = "Vista Previa de Evidencia"

    def prioridad_badge(self, obj):
        colores = {
            'Alta': '#d32f2f',
            'Media': '#f57c00',
            'Baja': '#2e7d32',
        }
        color = colores.get(obj.prioridad, '#555')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 9px; border-radius: 4px; font-weight: bold; font-size: 11px; letter-spacing: 0.5px;">{}</span>',
            color,
            obj.prioridad
        )
    prioridad_badge.short_description = "Prioridad"
    prioridad_badge.admin_order_field = 'prioridad'

    def estado_badge(self, obj):
        colores = {
            'capturado': '#0288d1',
            'en_revision': '#7b1fa2',
            'resuelto': '#2e7d32',
        }
        color = colores.get(obj.estado, '#555')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 9px; border-radius: 4px; font-weight: 500; font-size: 11px;">{}</span>',
            color,
            obj.get_estado_display() if hasattr(obj, 'get_estado_display') else obj.estado
        )
    estado_badge.short_description = "Estado"
    estado_badge.admin_order_field = 'estado'


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    """
    Gestión de personal minero y autorizaciones.
    """
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
                '<img src="{}" style="width: 38px; height: 38px; object-fit: cover; border-radius: 50%; border: 1px solid #ccc;" />',
                obj.foto_perfil.url
            )
        return mark_safe('<span style="color: #aaa; font-style: italic;">Sin avatar</span>')
    avatar_preview.short_description = "Avatar"

    def estado_badge(self, obj):
        color = '#2e7d32' if obj.estado == 'activo' else '#d32f2f'
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 12px;">● {}</span>',
            color,
            obj.estado.capitalize()
        )
    estado_badge.short_description = "Estado"


@admin.register(Localizacion)
class LocalizacionAdmin(admin.ModelAdmin):
    """
    Catálogo de sectores físicos de la faena minera.
    """
    list_display = ['id', 'nombre', 'activo_badge', 'updated_at']
    list_filter = ['activo']
    search_fields = ['nombre']

    def activo_badge(self, obj):
        color = '#2e7d32' if obj.activo else '#d32f2f'
        texto = 'Activo' if obj.activo else 'Inactivo'
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color,
            texto
        )
    activo_badge.short_description = "Estado"


@admin.register(ReporteHistorial)
class ReporteHistorialAdmin(admin.ModelAdmin):
    """
    Visor global de eventos de auditoría del sistema (inmutable).
    """
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
    list_filter = ['campo_modificado', ('fecha_cambio', admin.DateFieldListFilter)]
    search_fields = ['uuid', 'reporte__uuid', 'usuario_nombre', 'valor_nuevo']
    readonly_fields = [f.name for f in ReporteHistorial._meta.fields]
    date_hierarchy = 'fecha_cambio'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
