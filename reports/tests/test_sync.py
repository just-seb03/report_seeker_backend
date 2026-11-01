"""
Pruebas unitarias para Serializadores y Protocolo de Sincronización Idempotente (Fase 4).
"""

import uuid
from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from reports.models import Usuario, Localizacion, Reporte, ReporteHistorial
from reports.serializers import Base64ImageField


class Phase4SerializerAndSyncTests(TestCase):
    """
    Pruebas unitarias de serializadores, login de faena y sincronización bidireccional (Push/Pull).
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
        """Verifica inicio de sesión exitoso con ID y PIN válidos."""
        url = reverse('api_auth_login')
        response = self.client.post(url, {'usuario_id': 10482, 'pin': '1234'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['usuario']['usuario_id'], 10482)
        self.assertEqual(response.data['usuario']['nombre'], 'Sebastián Arredondo')

    def test_login_invalid_pin(self):
        """Rechaza login con PIN erróneo."""
        url = reverse('api_auth_login')
        response = self.client.post(url, {'usuario_id': 10482, 'pin': '9999'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_inactive_user(self):
        """Rechaza login para usuarios dados de baja (estado inactivo)."""
        self.usuario.estado = 'inactivo'
        self.usuario.save()
        url = reverse('api_auth_login')
        response = self.client.post(url, {'usuario_id': 10482, 'pin': '1234'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_parameters(self):
        """Rechaza login si faltan campos obligatorios."""
        url = reverse('api_auth_login')
        response = self.client.post(url, {'usuario_id': 10482}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sync_push_idempotency(self):
        """Verifica procesamiento idempotente en lote para reportes y auditoría sin duplicaciones."""
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
        """Verifica que el pull delta retorne únicamente registros modificados desde el timestamp 'since'."""
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

