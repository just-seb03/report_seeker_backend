"""
Modelos de Datos Relacionales del Servidor Central (Report Seeker).

Este módulo define la estructura de entidades para el control y gestión de incidencias:
- `Usuario`: Personal operativo y supervisores con credenciales de 5 dígitos y PIN.
- `Localizacion`: Catálogo maestro de áreas, sectores físicos y frentes de trabajo.
- `Reporte`: Registro de incidentes reportados (con fotografía, prioridad y estado).
- `ReporteHistorial`: Bitácora inmutable de auditoría para trazabilidad de modificaciones.
- `CodigoVerificacion`: Códigos OTP de 6 dígitos para recuperación segura de PIN vía correo.

Dónde se utiliza:
- En las vistas (`reports/views/`) y serializadores (`reports/serializers/`) para servir las APIs móviles y web.
- En el panel administrativo de Django (`reports/admin.py`) para supervisión y auditoría en faena.
- En la base de datos relacional SQLite del backend y reflejado en el SQLite local del dispositivo móvil.
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.hashers import check_password
from django.utils import timezone


class Usuario(models.Model):
    """
    Representa al personal operativo y supervisores de faena minera.
    
    Características clave:
    - `usuario_id`: Clave primaria numérica de 5 dígitos (entre 10000 y 99999).
    - `pin`: PIN numérico de 4 dígitos. Se almacena en texto plano en la base central
      para permitir la sincronización offline hacia las bases SQLite locales de los
      dispositivos móviles en faena sin conectividad.
    
    Especificación de arquitectura: BACKEND_SPEC.md § 3.1
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
        help_text="PIN de 4 dígitos (almacenado para sincronización offline con SQLite móvil)",
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

    def __str__(self) -> str:
        return f"{self.usuario_id} - {self.nombre} ({self.cargo})"

    def set_pin(self, raw_pin: str) -> None:
        """
        Establece el PIN del usuario.
        
        Guarda el valor limpio en texto plano para garantizar compatibilidad con la
        validación offline realizada por la app móvil en SQLite local.
        """
        self.pin = str(raw_pin).strip()

    def check_pin(self, raw_pin: str) -> bool:
        """
        Comprueba la validez de un PIN ingresado contra el registro del usuario.
        
        Soporta tanto comparación directa (texto plano) como verificación de hashes
        Django PBKDF2/Argon2 para compatibilidad total con cuentas heredadas.
        """
        raw_pin_str = str(raw_pin).strip()
        if self.pin == raw_pin_str:
            return True
        try:
            return check_password(raw_pin_str, self.pin)
        except Exception:
            return False


class Localizacion(models.Model):
    """
    Catálogo maestro de sectores físicos, frentes de trabajo y túneles en faena minera.
    
    Especificación de arquitectura: BACKEND_SPEC.md § 3.2
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

    def __str__(self) -> str:
        return str(self.nombre)


class Reporte(models.Model):
    """
    Entidad núcleo del sistema. Almacena las incidencias de seguridad reportadas en terreno.
    
    Especificación de arquitectura: BACKEND_SPEC.md § 3.3
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

    def __str__(self) -> str:
        return f"[{self.prioridad}] {self.titulo} ({self.uuid})"


class ReporteHistorial(models.Model):
    """
    Bitácora inmutable de auditoría que registra cada cambio efectuado sobre un reporte.
    
    Especificación de arquitectura: BACKEND_SPEC.md § 3.4
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

    def __str__(self) -> str:
        return f"Cambio en {self.campo_modificado} ({self.reporte.uuid})"


class CodigoVerificacion(models.Model):
    """
    Código OTP de 6 dígitos generado para la recuperación segura de PIN de acceso por correo.
    
    Características de seguridad:
    - Válido únicamente por un intervalo de tiempo acotado (15 minutos).
    - Limitador anti-fuerza bruta (máximo 5 intentos erróneos antes de ser invalidado).
    - Marca de un solo uso (`utilizado=True`) al consumirse exitosamente.
    """
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="UUID Código"
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='codigos_verificacion',
        verbose_name="Usuario"
    )
    correo = models.EmailField(verbose_name="Correo al que fue enviado")
    codigo = models.CharField(max_length=6, verbose_name="Código de 6 dígitos")
    expira_en = models.DateTimeField(verbose_name="Fecha y hora de expiración")
    utilizado = models.BooleanField(default=False, verbose_name="¿Ya fue utilizado?")
    intentos = models.PositiveSmallIntegerField(default=0, verbose_name="Intentos fallidos")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Código de Verificación"
        verbose_name_plural = "Códigos de Verificación"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['usuario', 'utilizado']),
            models.Index(fields=['expira_en']),
        ]

    def es_valido(self) -> bool:
        """
        Determina si el código OTP está vigente y disponible para verificación:
        - No haber sido consumido previamente.
        - No haber sobrepasado su fecha y hora límite de expiración.
        - No haber excedido el umbral máximo de 5 intentos erróneos.
        """
        return not self.utilizado and timezone.now() <= self.expira_en and self.intentos < 5

    def __str__(self) -> str:
        estado = "Utilizado" if self.utilizado else ("Válido" if self.es_valido() else "Expirado")
        return f"OTP {self.codigo} para #{self.usuario_id} ({estado})"
