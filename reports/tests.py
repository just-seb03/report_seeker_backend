import uuid
from datetime import timedelta
from django.contrib.admin.sites import site as admin_site
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from reports.models import Usuario, Localizacion, Reporte, ReporteHistorial
from reports.serializers import Base64ImageField


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
        """Verifica la representación de cadenas de los modelos."""
        self.assertIn("10482 - Sebastián Arredondo", str(self.usuario))
        self.assertEqual("Nivel Central - Túnel 4", str(self.localizacion))

        reporte = Reporte.objects.create(
            titulo='Incidente prueba',
            fecha_captura=timezone.now(),
            prioridad='Alta'
        )
        self.assertIn("[Alta] Incidente prueba", str(reporte))


class Phase4SerializerAndSyncTests(TestCase):
    """
    Pruebas unitarias de la Fase 4 (Serializers y Lógica de Sincronización Idempotente)
    """
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
        # 1x1 pixel transparent PNG in Base64
        self.dummy_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

    def test_base64_image_field_decoding(self):
        """Verifica que Base64ImageField decodifique correctamente strings Base64 a ContentFile."""
        field = Base64ImageField()
        file_obj = field.to_internal_value(self.dummy_base64)
        self.assertIsNotNone(file_obj)
        self.assertTrue(file_obj.name.endswith('.png'))
        self.assertGreater(file_obj.size, 0)

    def test_base64_image_field_invalid(self):
        """Verifica que strings no Base64 levanten ValidationError."""
        field = Base64ImageField()
        from rest_framework.exceptions import ValidationError as DRFValidationError
        with self.assertRaises(DRFValidationError):
            field.to_internal_value(12345)

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

    def test_login_inactive_user(self):
        self.usuario.estado = 'inactivo'
        self.usuario.save()
        url = reverse('api_auth_login')
        response = self.client.post(url, {'usuario_id': 10482, 'pin': '1234'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_parameters(self):
        url = reverse('api_auth_login')
        response = self.client.post(url, {'usuario_id': 10482}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sync_push_idempotency(self):
        push_url = reverse('api_sync_push')
        rep_uuid = str(uuid.uuid4())
        hist_uuid = str(uuid.uuid4())

        payload = {
            "reportes": [
                {
                    "local_id": 1,
                    "uuid": rep_uuid,
                    "titulo": "Fuga de aceite en motor",
                    "descripcion": "Goteo detectado en faena",
                    "fotografia_base64": self.dummy_base64,
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

        # 1er Push
        response = self.client.post(push_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Reporte.objects.count(), 1)
        self.assertEqual(ReporteHistorial.objects.count(), 1)

        rep = Reporte.objects.get(uuid=rep_uuid)
        self.assertEqual(rep.titulo, "Fuga de aceite en motor")
        self.assertTrue(bool(rep.fotografia))

        # 2do Push con modificación sobre el mismo reporte (mismo UUID)
        payload["reportes"][0]["titulo"] = "Fuga de aceite en motor reparada"
        payload["reportes"][0]["estado"] = "resuelto"
        response2 = self.client.post(push_url, payload, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # La idempotencia asegura que NO se creen duplicados
        self.assertEqual(Reporte.objects.count(), 1)
        self.assertEqual(ReporteHistorial.objects.count(), 1)

        rep.refresh_from_db()
        self.assertEqual(rep.titulo, "Fuga de aceite en motor reparada")
        self.assertEqual(rep.estado, "resuelto")

    def test_sync_pull_delta(self):
        Reporte.objects.create(
            uuid=uuid.uuid4(),
            titulo='Incidente Antiguo',
            fecha_captura=timezone.now() - timedelta(days=5),
            prioridad='Baja',
            estado='resuelto'
        )

        checkpoint = timezone.now() - timedelta(seconds=1)

        recent_rep = Reporte.objects.create(
            uuid=uuid.uuid4(),
            titulo='Incidente Reciente',
            fecha_captura=timezone.now(),
            prioridad='Alta',
            estado='capturado'
        )

        pull_url = reverse('api_sync_pull')
        response = self.client.get(f"{pull_url}?since={checkpoint.isoformat()}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('catalogos', response.data)
        self.assertIn('reportes', response.data)

        report_uuids = [r['uuid'] for r in response.data['reportes']]
        self.assertIn(str(recent_rep.uuid), report_uuids)


class Phase5DjangoAdminTests(TestCase):
    """
    Pruebas unitarias de la Fase 5 (Django Admin de Alta Usabilidad para Supervisores)
    """
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin_tester',
            email='admin@test.cl',
            password='password123'
        )
        self.client.force_login(self.admin_user)

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
        self.reporte = Reporte.objects.create(
            titulo='Derrame de Combustible',
            descripcion='Fuga en estanque auxiliar',
            fecha_captura=timezone.now(),
            usuario=self.usuario,
            localizacion=self.localizacion,
            prioridad='Alta',
            estado='capturado'
        )
        self.historial = ReporteHistorial.objects.create(
            reporte=self.reporte,
            usuario=self.usuario,
            usuario_nombre=self.usuario.nombre,
            campo_modificado='estado',
            valor_anterior='capturado',
            valor_nuevo='en_revision',
            fecha_cambio=timezone.now()
        )

    def test_models_registered_in_admin(self):
        """Verifica que todos los modelos estén registrados en el admin."""
        self.assertIn(Reporte, admin_site._registry)
        self.assertIn(Usuario, admin_site._registry)
        self.assertIn(Localizacion, admin_site._registry)
        self.assertIn(ReporteHistorial, admin_site._registry)

    def test_reporte_admin_changelist_view(self):
        """Verifica que la lista de reportes cargue con código 200 en el admin."""
        url = reverse('admin:reports_reporte_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, 'Derrame de Combustible')
        self.assertContains(response, 'Nivel Central - Túnel 4')

    def test_reporte_admin_change_view_with_inlines(self):
        """Verifica que la ficha de detalle de reporte cargue el historial en el TabularInline."""
        url = reverse('admin:reports_reporte_change', args=[self.reporte.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, 'en_revision')
        self.assertContains(response, 'Sebastián Arredondo')

    def test_admin_actions(self):
        """Verifica la acción de cambio de estado en lote a 'Resuelto'."""
        reporte_admin = admin_site._registry[Reporte]
        queryset = Reporte.objects.filter(pk=self.reporte.pk)
        reporte_admin.marcar_resuelto(None, queryset)
        self.reporte.refresh_from_db()
        self.assertEqual(self.reporte.estado, 'resuelto')
