"""
Pruebas unitarias para el comando de gestión de datos semilla (seed_data).
"""

from io import StringIO
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from reports.models import Localizacion, Usuario


class Phase6SeedDataTests(TestCase):
    """
    Verifica la ejecución inicial e idempotente del comando seed_data.
    """
    def test_seed_data_execution_and_idempotency(self):
        """Verifica que seed_data inserte los registros iniciales y no falle al re-ejecutarse."""
        out = StringIO()
        # 1era ejecución
        call_command('seed_data', with_admin=True, stdout=out)
        output = out.getvalue()

        self.assertIn('Carga completada con éxito', output)
        self.assertEqual(Localizacion.objects.count(), 4)
        self.assertEqual(Usuario.objects.count(), 3)
        self.assertTrue(User.objects.filter(username='admin', is_superuser=True).exists())

        # Verificar datos específicos de seed
        seb = Usuario.objects.get(usuario_id=10482)
        self.assertEqual(seb.nombre, 'Sebastián Arredondo')
        self.assertEqual(seb.cargo, 'Prevencionista de Riesgos')
        self.assertTrue(seb.habilitar_sumario)
        self.assertEqual(seb.pin, '1234')

        carlos = Usuario.objects.get(usuario_id=48291)
        self.assertFalse(carlos.habilitar_sumario)

        # 2da ejecución (idempotencia)
        out2 = StringIO()
        call_command('seed_data', stdout=out2)
        self.assertEqual(Localizacion.objects.count(), 4)
        self.assertEqual(Usuario.objects.count(), 3)

