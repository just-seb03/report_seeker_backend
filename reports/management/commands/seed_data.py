from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from reports.models import Localizacion, Usuario


DEFAULT_LOCALIZACIONES = [
    {'id': 1, 'nombre': 'Nivel Central - Túnel 4'},
    {'id': 2, 'nombre': 'Taller de Chancado'},
    {'id': 3, 'nombre': 'Plataforma Norte'},
    {'id': 4, 'nombre': 'Campamento Los Aromos'},
]

DEFAULT_USUARIOS = [
    {
        'usuario_id': 10482,
        'nombre': 'Sebastián Arredondo',
        'correo': 'sebastian@minera.cl',
        'cargo': 'Prevencionista de Riesgos',
        'pin': '1234',
        'habilitar_sumario': True,
        'estado': 'activo',
    },
    {
        'usuario_id': 48291,
        'nombre': 'Carlos Mendoza',
        'correo': 'carlos.mendoza@minera.cl',
        'cargo': 'Supervisor de Turno Mina',
        'pin': '4321',
        'habilitar_sumario': False,
        'estado': 'activo',
    },
    {
        'usuario_id': 73915,
        'nombre': 'Valentina Soto',
        'correo': 'valentina.soto@minera.cl',
        'cargo': 'Ingeniera de Seguridad Ocupacional',
        'pin': '5678',
        'habilitar_sumario': True,
        'estado': 'activo',
    },
]


class Command(BaseCommand):
    help = 'Puebla la base de datos con localizaciones y usuarios iniciales de faena'

    def handle(self, *args, **options):
        self.stdout.write("Sembrando localizaciones iniciales...")
        for loc in DEFAULT_LOCALIZACIONES:
            obj, created = Localizacion.objects.update_or_create(
                id=loc['id'],
                defaults={'nombre': loc['nombre'], 'activo': True}
            )
            accion = "Creada" if created else "Actualizada"
            self.stdout.write(f" - [{accion}] Localización #{obj.id}: {obj.nombre}")

        self.stdout.write("\nSembrando usuarios iniciales...")
        for u in DEFAULT_USUARIOS:
            user_obj, created = Usuario.objects.update_or_create(
                usuario_id=u['usuario_id'],
                defaults={
                    'nombre': u['nombre'],
                    'correo': u['correo'],
                    'cargo': u['cargo'],
                    'pin': u['pin'],
                    'habilitar_sumario': u['habilitar_sumario'],
                    'estado': u['estado'],
                }
            )
            # Asegurar usuario Django para autenticación DRF si se requiere
            django_user, _ = User.objects.get_or_create(
                username=str(user_obj.usuario_id),
                defaults={'first_name': user_obj.nombre, 'email': user_obj.correo}
            )
            django_user.set_password(u['pin'])
            django_user.save()

            accion = "Creado" if created else "Actualizado"
            self.stdout.write(f" - [{accion}] Usuario #{user_obj.usuario_id}: {user_obj.nombre} ({user_obj.cargo})")

        self.stdout.write(self.style.SUCCESS("\n¡Base de datos sembrada exitosamente!"))

