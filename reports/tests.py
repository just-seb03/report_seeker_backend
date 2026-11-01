import uuid
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from reports.models import Usuario, Localizacion, Reporte, ReporteHistorial


class ModelIntegrityTests(TestCase):
    """
    Pruebas unitarias de integridad de la Fase 3 (Modelo de Datos Relacional - BACKEND_SPEC.md § 3)
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
        """Verifica que el usuario_id deba ser de 5 dígitos (10000 - 99999)."""
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

    def test_usuario_pin_hashing(self):
        """Verifica que set_pin hashee la clave y check_pin valide correctamente."""
        user = Usuario.objects.create(
            usuario_id=55555,
            nombre='Tester Hasher',
            correo='tester@minera.cl',
            cargo='Tecnico',
            pin='temp'
        )
        user.set_pin('9876')
        user.save()

        self.assertNotEqual(user.pin, '9876')
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
        reporte = Reporte.objects.create(
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
        """Verifica la representación de cadenas de los modelos."""
        self.assertIn("10482 - Sebastián Arredondo", str(self.usuario))
        self.assertEqual("Nivel Central - Túnel 4", str(self.localizacion))

        reporte = Reporte.objects.create(
            titulo='Incidente prueba',
            fecha_captura=timezone.now(),
            prioridad='Alta'
        )
        self.assertIn("[Alta] Incidente prueba", str(reporte))


class SyncApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
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

    def test_login_success(self):
        url = reverse('api_auth_login')
        response = self.client.post(url, {'usuario_id': 10482, 'pin': '1234'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['usuario']['usuario_id'], 10482)
        self.assertEqual(response.data['usuario']['nombre'], 'Sebastián Arredondo')

    def test_login_invalid_pin(self):
        url = reverse('api_auth_login')
        response = self.client.post(url, {'usuario_id': 10482, 'pin': '9999'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sync_push_and_pull(self):
        push_url = reverse('api_sync_push')
        rep_uuid = str(uuid.uuid4())
        hist_uuid = str(uuid.uuid4())

        # 1x1 pixel transparent PNG in Base64
        dummy_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

        payload = {
            "reportes": [
                {
                    "local_id": 1,
                    "uuid": rep_uuid,
                    "titulo": "Fuga de aceite en motor",
                    "descripcion": "Goteo detectado durante inspección matutina",
                    "fotografia_base64": dummy_base64,
                    "fecha_captura": "2026-10-31T18:00:00Z",
                    "usuario_id": 10482,
                    "ubicacion_id": 1,
                    "prioridad": "Alta",
                    "estado": "capturado"
                }
            ],
            "historial": [
                {
                    "local_id": 10,
                    "uuid": hist_uuid,
                    "reporte_uuid": rep_uuid,
                    "usuario_id": 10482,
                    "usuario_nombre": "Sebastián Arredondo",
                    "campo_modificado": "prioridad",
                    "valor_anterior": "Media",
                    "valor_nuevo": "Alta",
                    "fecha_cambio": "2026-10-31T18:15:00Z"
                }
            ]
        }

        # First Push
        response = self.client.post(push_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['synced_reports']), 1)
        self.assertEqual(len(response.data['synced_historial']), 1)
        self.assertEqual(Reporte.objects.count(), 1)
        self.assertEqual(ReporteHistorial.objects.count(), 1)

        rep = Reporte.objects.get(uuid=rep_uuid)
        self.assertEqual(rep.titulo, "Fuga de aceite en motor")
        self.assertTrue(bool(rep.fotografia))

        # Idempotent push (same data sent again)
        response2 = self.client.post(push_url, payload, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(Reporte.objects.count(), 1)
        self.assertEqual(ReporteHistorial.objects.count(), 1)

        # Pull
        pull_url = reverse('api_sync_pull')
        pull_response = self.client.get(pull_url)
        self.assertEqual(pull_response.status_code, status.HTTP_200_OK)
        self.assertIn('catalogos', pull_response.data)
        self.assertIn('reportes', pull_response.data)
        self.assertEqual(len(pull_response.data['reportes']), 1)
        self.assertEqual(pull_response.data['reportes'][0]['uuid'], rep_uuid)
