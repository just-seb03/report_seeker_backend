import uuid
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from reports.models import Usuario, Localizacion, Reporte, ReporteHistorial


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
