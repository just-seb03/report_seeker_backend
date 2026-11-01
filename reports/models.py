import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.hashers import make_password, check_password


class Usuario(models.Model):
    """
    Representa al personal operativo y supervisores de faena minera.
    Especificación: BACKEND_SPEC.md § 3.1
    """
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
    ]

    usuario_id = models.PositiveIntegerField(
        primary_key=True,
        validators=[
            MinValueValidator(10000, message="El usuario_id debe ser de al menos 5 dígitos (>= 10000)"),
            MaxValueValidator(99999, message="El usuario_id no debe exceder 5 dígitos (<= 99999)")
        ],
        help_text="ID de credencial de 5 dígitos (ej. 10482)",
        verbose_name="ID de credencial"
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre completo")
    correo = models.EmailField(unique=True, verbose_name="Correo corporativo")
    cargo = models.CharField(max_length=100, verbose_name="Cargo / Especialidad")
    foto_perfil = models.ImageField(
        upload_to='perfiles/',
        null=True,
        blank=True,
        verbose_name="Foto de perfil"
    )
    pin = models.CharField(
        max_length=128,
        help_text="PIN de 4 dígitos (hasheado con PBKDF2/Argon2 o texto plano para compatibilidad)",
        verbose_name="PIN de acceso"
    )
    habilitar_sumario = models.BooleanField(
        default=True,
        verbose_name="Habilitar gestión/sumario"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='activo',
        verbose_name="Estado laboral"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ['usuario_id']
        indexes = [
            models.Index(fields=['correo']),
            models.Index(fields=['estado']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"{self.usuario_id} - {self.nombre} ({self.cargo})"

    def set_pin(self, raw_pin: str):
        """Guarda el PIN de 4 dígitos en texto plano para compatibilidad con la app móvil offline."""
        self.pin = str(raw_pin).strip()

    def check_pin(self, raw_pin: str) -> bool:
        """Comprueba el PIN tanto si está en texto plano como hasheado."""
        raw_pin_str = str(raw_pin).strip()
        if self.pin == raw_pin_str:
            return True
        try:
            return check_password(raw_pin_str, self.pin)
        except Exception:
            return False


class Localizacion(models.Model):
    """
    Catálogo maestro de sectores y áreas físicas de la faena minera.
    Especificación: BACKEND_SPEC.md § 3.2
    """
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Nombre del sector")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    class Meta:
        verbose_name = "Localización"
        verbose_name_plural = "Localizaciones"
        ordering = ['id']
        indexes = [
            models.Index(fields=['nombre']),
            models.Index(fields=['activo']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return str(self.nombre)


class Reporte(models.Model):
    """
    Núcleo del sistema. Almacena las incidencias reportadas.
    Especificación: BACKEND_SPEC.md § 3.3
    """
    PRIORIDAD_CHOICES = [
        ('Alta', 'Alta'),
        ('Media', 'Media'),
        ('Baja', 'Baja'),
    ]

    ESTADO_CHOICES = [
        ('capturado', 'Capturado'),
        ('en_revision', 'En Revisión'),
        ('resuelto', 'Resuelto'),
    ]

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        verbose_name="UUID Universal"
    )
    titulo = models.CharField(max_length=255, verbose_name="Título del reporte")
    descripcion = models.TextField(blank=True, default='', verbose_name="Descripción")
    fotografia = models.ImageField(
        upload_to='reportes/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Fotografía adjunta"
    )
    fecha_captura = models.DateTimeField(verbose_name="Fecha de captura")
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='reportes',
        verbose_name="Usuario autor"
    )
    usuario_nombre = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name="Nombre del autor (desnormalizado)"
    )
    usuario_cargo = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Cargo del autor (desnormalizado)"
    )
    localizacion = models.ForeignKey(
        Localizacion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reportes',
        verbose_name="Localización formal"
    )
    ubicacion_texto = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name="Ubicación texto"
    )
    prioridad = models.CharField(
        max_length=20,
        choices=PRIORIDAD_CHOICES,
        default='Media',
        verbose_name="Prioridad"
    )
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_CHOICES,
        default='capturado',
        verbose_name="Estado de ciclo de vida"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de recepción en servidor"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        verbose_name="Última modificación"
    )

    class Meta:
        verbose_name = "Reporte"
        verbose_name_plural = "Reportes"
        ordering = ['-fecha_captura']
        indexes = [
            models.Index(fields=['fecha_captura']),
            models.Index(fields=['prioridad']),
            models.Index(fields=['estado']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"[{self.prioridad}] {self.titulo} ({self.uuid})"


class ReporteHistorial(models.Model):
    """
    Bitácora inmutable de cambios y modificaciones sobre los reportes.
    Especificación: BACKEND_SPEC.md § 3.4
    """
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        verbose_name="UUID Evento Auditoría"
    )
    reporte = models.ForeignKey(
        Reporte,
        on_delete=models.CASCADE,
        related_name='historial',
        verbose_name="Reporte vinculado"
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='historiales',
        verbose_name="Usuario que modificó"
    )
    usuario_nombre = models.CharField(
        max_length=150,
        verbose_name="Nombre archivado del operador"
    )
    campo_modificado = models.CharField(
        max_length=50,
        verbose_name="Campo modificado"
    )
    valor_anterior = models.TextField(
        null=True,
        blank=True,
        verbose_name="Valor anterior"
    )
    valor_nuevo = models.TextField(verbose_name="Valor nuevo")
    fecha_cambio = models.DateTimeField(verbose_name="Fecha original del cambio")
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de sincronización al servidor"
    )

    class Meta:
        verbose_name = "Historial de Reporte"
        verbose_name_plural = "Historiales de Reportes"
        ordering = ['-fecha_cambio']
        indexes = [
            models.Index(fields=['fecha_cambio']),
            models.Index(fields=['reporte', 'fecha_cambio']),
        ]

    def __str__(self):
        return f"Cambio en {self.campo_modificado} ({self.reporte.uuid})"
