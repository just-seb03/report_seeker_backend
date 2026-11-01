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
        'correo': 'seb.arredondo@proton.me',
        'cargo': 'Prevencionista de Riesgos',
        'foto_perfil': None,
        'pin': '1234',
        'habilitar_sumario': True,
        'estado': 'activo',
    },
    {
        'usuario_id': 48291,
        'nombre': 'Carlos Mendoza',
        'correo': 'carlos.mendoza@minera.cl',
        'cargo': 'Supervisor de Turno Mina',
        'foto_perfil': None,
        'pin': '4321',
        'habilitar_sumario': False,
        'estado': 'activo',
    },
    {
        'usuario_id': 73915,
        'nombre': 'Valentina Soto',
        'correo': 'valentina.soto@minera.cl',
        'cargo': 'Ingeniera de Seguridad Ocupacional',
        'foto_perfil': None,
        'pin': '5678',
        'habilitar_sumario': True,
        'estado': 'activo',
    },
]


class Command(BaseCommand):
    help = (
        'Carga los datos maestros iniciales (Seeds) para poblar la base de datos central '
        'de la laptop con los usuarios y sectores mineros predeterminados (según seed.sql.ts).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-admin',
            action='store_true',
            help='Crea o actualiza también el superusuario admin inicial para el Django Admin (admin / admin1234)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Iniciando carga de semillas (Seed Data) para Report Seeker..."))

        # 1. Sembrar Localizaciones
        self.stdout.write("\n1. Sembrando catálogo maestro de localizaciones...")
        loc_creadas = 0
        loc_actualizadas = 0

        for loc in DEFAULT_LOCALIZACIONES:
            obj, created = Localizacion.objects.update_or_create(
                id=loc['id'],
                defaults={'nombre': loc['nombre'], 'activo': True}
            )
            if created:
                loc_creadas += 1
                estado_txt = self.style.SUCCESS("[CREADA]")
            else:
                loc_actualizadas += 1
                estado_txt = self.style.WARNING("[ACTUALIZADA]")

            self.stdout.write(f"   {estado_txt} Localización #{obj.id}: {obj.nombre}")

        # 2. Sembrar Usuarios
        self.stdout.write("\n2. Sembrando perfiles iniciales de trabajadores y supervisores...")
        user_creados = 0
        user_actualizados = 0

        for u in DEFAULT_USUARIOS:
            user_obj, created = Usuario.objects.update_or_create(
                usuario_id=u['usuario_id'],
                defaults={
                    'nombre': u['nombre'],
                    'correo': u['correo'],
                    'cargo': u['cargo'],
                    'foto_perfil': u['foto_perfil'],
                    'pin': u['pin'],
                    'habilitar_sumario': u['habilitar_sumario'],
                    'estado': u['estado'],
                }
            )

            # Sincronizar cuenta Django User para autenticación DRF vía token
            django_user, _ = User.objects.get_or_create(
                username=str(user_obj.usuario_id),
                defaults={'first_name': user_obj.nombre, 'email': user_obj.correo}
            )
            django_user.set_password(u['pin'])
            django_user.save()

            if created:
                user_creados += 1
                estado_txt = self.style.SUCCESS("[CREADO]")
            else:
                user_actualizados += 1
                estado_txt = self.style.WARNING("[ACTUALIZADO]")

            self.stdout.write(
                f"   {estado_txt} Usuario #{user_obj.usuario_id}: {user_obj.nombre} "
                f"({user_obj.cargo}) - PIN: {u['pin']}"
            )

        # 3. Superusuario opcional
        if options.get('with_admin'):
            self.stdout.write("\n3. Verificando superusuario administrador...")
            admin_user, admin_created = User.objects.get_or_create(
                username='admin',
                defaults={'email': 'admin@reportseeker.local', 'is_staff': True, 'is_superuser': True}
            )
            admin_user.set_password('admin1234')
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
            admin_txt = "[CREADO]" if admin_created else "[ACTUALIZADO]"
            self.stdout.write(f"   {self.style.SUCCESS(admin_txt)} Superuser: admin (clave: admin1234)")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Carga completada con éxito: {len(DEFAULT_LOCALIZACIONES)} localizaciones "
                f"y {len(DEFAULT_USUARIOS)} usuarios operativos listos."
            )
        )
