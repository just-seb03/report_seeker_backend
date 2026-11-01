"""
Pruebas unitarias para el Panel de Administración Django (Fase 5).
"""

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from reports.models import Usuario, Localizacion, Reporte, ReporteHistorial


class Phase5DjangoAdminTests(TestCase):
    """
    Verifica registro de modelos, vistas changelist, inlines y acciones en lote del panel.
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
        """Verifica que todos los modelos del dominio estén registrados en el panel."""
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
        """Verifica la acción administrativa de cambio de estado en lote a 'Resuelto'."""
        reporte_admin = admin_site._registry[Reporte]
        queryset = Reporte.objects.filter(pk=self.reporte.pk)
        reporte_admin.marcar_resuelto(None, queryset)
        self.reporte.refresh_from_db()
        self.assertEqual(self.reporte.estado, 'resuelto')

