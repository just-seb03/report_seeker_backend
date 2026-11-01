"""
Pruebas unitarias de integridad para el Modelo de Datos Relacional (Fase 3).
"""

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone
from reports.models import Usuario, Localizacion, Reporte, ReporteHistorial


class ModelIntegrityTests(TestCase):
    """
    Verifica las restricciones de esquema, validadores y relaciones de clave foránea.
    """
    def setUp(self):
        self.usuario = Usuario.objects.create(
            usuario_id=10482,
            nombre='Sebastián Arredondo',
            correo='sebastian@minera.cl',
            cargo='Prevencionista de Riesgos',
            pin='1234',
            habilitar_sumario=True,
            estado='activo',
        )
        self.localizacion = Localizacion.objects.create(
            id=1,
            nombre='Nivel Central - Túnel 4',
            activo=True
        )

    def test_usuario_id_validation(self):
        """Verifica que el usuario_id deba ser exactamente de 5 dígitos (10000 - 99999)."""
        invalid_user_low = Usuario(
            usuario_id=999,
            nombre='Test',
            correo='test_low@minera.cl',
            cargo='Operador',
            pin='1234'
        )
        with self.assertRaises(ValidationError):
            invalid_user_low.full_clean()

        invalid_user_high = Usuario(
            usuario_id=100000,
            nombre='Test',
            correo='test_high@minera.cl',
            cargo='Operador',
            pin='1234'
        )
        with self.assertRaises(ValidationError):
            invalid_user_high.full_clean()

    def test_usuario_pin_storage_and_validation(self):
        """Verifica almacenamiento de PIN en texto plano para sync offline y validación correcta."""
        user = Usuario.objects.create(
            usuario_id=55555,
            nombre='Tester Hasher',
            correo='tester@minera.cl',
            cargo='Tecnico',
            pin='temp'
        )
        user.set_pin('9876')
        user.save()

        self.assertEqual(user.pin, '9876')
        self.assertTrue(user.check_pin('9876'))
        self.assertFalse(user.check_pin('0000'))

    def test_unique_constraints(self):
        """Verifica unicidad de correo en Usuario y nombre en Localizacion."""
        from django.db import transaction
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Usuario.objects.create(
                    usuario_id=20000,
                    nombre='Duplicado',
                    correo='sebastian@minera.cl',  # Ya existente
                    cargo='Operador',
                    pin='1234'
                )

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Localizacion.objects.create(
                    nombre='Nivel Central - Túnel 4'  # Ya existente
                )

    def test_foreign_key_protection_usuario(self):
        """Un usuario con reportes asociados no puede ser eliminado (on_delete=PROTECT)."""
        Reporte.objects.create(
            titulo='Peligro de caída de rocas',
            fecha_captura=timezone.now(),
            usuario=self.usuario,
            localizacion=self.localizacion,
            prioridad='Alta',
            estado='capturado'
        )
        with self.assertRaises(ProtectedError):
            self.usuario.delete()

    def test_cascade_delete_reporte_historial(self):
        """Al eliminar un reporte, su historial vinculado debe eliminarse en cascada."""
        reporte = Reporte.objects.create(
            titulo='Derrame de refrigerante',
            fecha_captura=timezone.now(),
            usuario=self.usuario,
            localizacion=self.localizacion,
            prioridad='Media',
            estado='capturado'
        )
        ReporteHistorial.objects.create(
            reporte=reporte,
            usuario=self.usuario,
            usuario_nombre=self.usuario.nombre,
            campo_modificado='prioridad',
            valor_anterior='Baja',
            valor_nuevo='Media',
            fecha_cambio=timezone.now()
        )
        self.assertEqual(ReporteHistorial.objects.filter(reporte=reporte).count(), 1)
        reporte.delete()
        self.assertEqual(ReporteHistorial.objects.count(), 0)

    def test_str_representations(self):
        """Verifica la representación de cadenas (__str__) de los modelos."""
        self.assertIn("10482 - Sebastián Arredondo", str(self.usuario))
        self.assertEqual("Nivel Central - Túnel 4", str(self.localizacion))

        reporte = Reporte.objects.create(
            titulo='Incidente prueba',
            fecha_captura=timezone.now(),
            prioridad='Alta'
        )
        self.assertIn("[Alta] Incidente prueba", str(reporte))

