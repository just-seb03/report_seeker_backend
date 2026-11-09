"""
Pruebas Unitarias para controladores CRUD con ModelViewSet y DefaultRouter.

Este archivo valida las 5 operaciones fundamentales de la API navegable de DRF:
1. Listado general de reportes (`GET /api/v1/reportes/`).
2. Creación de un nuevo reporte (`POST /api/v1/reportes/`).
3. Consulta detallada de una incidencia (`GET /api/v1/reportes/<pk>/`).
4. Actualización completa o parcial de datos (`PUT /api/v1/reportes/<pk>/`).
5. Eliminación de un reporte del sistema (`DELETE /api/v1/reportes/<pk>/`).

Dónde se utiliza:
- En la suite de pruebas automatizadas del proyecto (`python manage.py test reports.tests.test_crud_viewsets`).
- Valida el comportamiento de `ReporteViewSet` y `LocalizacionViewSet` expuestos en `reports/urls.py`.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from reports.models import Reporte, Localizacion, Usuario


class ViewSetCrudTests(TestCase):
    """
    Verifica que los ViewSets conectados al DefaultRouter cumplan correctamente
    con las operaciones estándar de la API REST.
    """
    def setUp(self):
        self.client = APIClient()
        self.usuario = Usuario.objects.create(
            usuario_id=10482,
            nombre='Sebastián Arredondo',
            correo='seb.arredondo@proton.me',
            cargo='Prevencionista',
            pin='1234',
            estado='activo',
        )
        self.localizacion = Localizacion.objects.create(
            id=1,
            nombre='Túnel 4',
            activo=True,
        )
        self.reporte = Reporte.objects.create(
            titulo='Incidencia Inicial',
            descripcion='Descripción de prueba',
            fecha_captura=timezone.now(),
            usuario=self.usuario,
            localizacion=self.localizacion,
            prioridad='Media',
            estado='capturado',
        )

    def test_api_root_lists_registered_viewsets(self):
        """Verifica que el router exponga los endpoints principales en la raíz de la API."""
        response = self.client.get('/api/v1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reportes', response.data)
        self.assertIn('localizaciones', response.data)

    def test_reporte_list_get(self):
        """Verifica listar reportes (GET /api/v1/reportes/)."""
        response = self.client.get('/api/v1/reportes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 1)

    def test_reporte_list_filters_by_prioridad_and_estado(self):
        """Verifica filtrar reportes por prioridad y estado."""
        Reporte.objects.create(
            titulo='Reporte no coincidente',
            descripcion='No debe aparecer en el resultado filtrado',
            fecha_captura=timezone.now(),
            usuario=self.usuario,
            localizacion=self.localizacion,
            prioridad='Alta',
            estado='en_revision',
        )

        response = self.client.get(
            '/api/v1/reportes/?prioridad=Media&estado=capturado'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['titulo'], 'Incidencia Inicial')

    def test_reporte_list_supports_page_size_with_maximum(self):
        """Verifica page_size configurable con un límite máximo de 100 registros."""
        Reporte.objects.bulk_create([
            Reporte(
                titulo=f'Reporte de paginación {index}',
                descripcion='Reporte para probar paginación',
                fecha_captura=timezone.now(),
                usuario=self.usuario,
                localizacion=self.localizacion,
                prioridad='Media',
                estado='capturado',
            )
            for index in range(101)
        ])

        response = self.client.get('/api/v1/reportes/?page_size=1')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 102)
        self.assertEqual(len(response.data['results']), 1)

        response = self.client.get('/api/v1/reportes/?page_size=200')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 100)

    def test_reporte_create_post(self):
        """Verifica crear un reporte mediante POST."""
        payload = {
            'titulo': 'Nuevo Reporte DRF',
            'descripcion': 'Creado desde ModelViewSet',
            'fecha_captura': timezone.now().isoformat(),
            'prioridad': 'Alta',
            'estado': 'capturado',
            'localizacion': self.localizacion.id,
            'usuario': self.usuario.usuario_id,
        }
        response = self.client.post('/api/v1/reportes/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['titulo'], 'Nuevo Reporte DRF')

    def test_reporte_detail_get(self):
        """Verifica obtener detalle de un registro específico (GET /api/v1/reportes/<pk>/)."""
        response = self.client.get(f'/api/v1/reportes/{self.reporte.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['titulo'], 'Incidencia Inicial')

    def test_reporte_update_put(self):
        """Verifica actualizar un registro existente (PUT /api/v1/reportes/<pk>/)."""
        payload = {
            'titulo': 'Incidencia Modificada',
            'descripcion': 'Actualizada vía PUT',
            'fecha_captura': self.reporte.fecha_captura.isoformat(),
            'prioridad': 'Alta',
            'estado': 'en_revision',
        }
        response = self.client.put(f'/api/v1/reportes/{self.reporte.pk}/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.reporte.refresh_from_db()
        self.assertEqual(self.reporte.titulo, 'Incidencia Modificada')
        self.assertEqual(self.reporte.prioridad, 'Alta')

    def test_reporte_delete(self):
        """Verifica eliminar un registro (DELETE /api/v1/reportes/<pk>/)."""
        response = self.client.delete(f'/api/v1/reportes/{self.reporte.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Reporte.objects.filter(pk=self.reporte.pk).exists())
