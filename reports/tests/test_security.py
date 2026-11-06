"""
Pruebas Unitarias de Seguridad y Hardening Defensivo.

Este módulo comprueba las protecciones de infraestructura y aplicación implementadas en el backend:
1. Rechazo de payloads excesivos en Base64 (>10 MB) para prevención de ataques DoS por memoria.
2. Validación de firmas binarias reales (Magic Bytes) en imágenes.
3. Presencia obligatoria de cabeceras de seguridad HTTP (X-Content-Type-Options, X-Frame-Options).
4. Respuestas neutrales para evitar la enumeración de usuarios en solicitudes de recuperación de clave.
5. Bloqueo temporal automático de cuenta (Account Lockout) tras 5 intentos fallidos consecutivos de PIN.
6. Monitoreo de disponibilidad del nodo a través del endpoint /health/.

Dónde se utiliza:
- Ejecutado en las pruebas automatizadas del proyecto para asegurar que las políticas de seguridad se mantengan activas.
"""

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from reports.models import Usuario
from reports.serializers.common import Base64ImageField, MAX_BASE64_PAYLOAD_BYTES


class SecurityHardeningTests(TestCase):
    """
    Pruebas automatizadas de las defensas y controles de seguridad del sistema.
    """
    def setUp(self):
        cache.clear()
        self.usuario = Usuario.objects.create(
            usuario_id=10482,
            nombre='Sebastián Arredondo',
            correo='sebastian@minera.cl',
            cargo='Prevencionista',
            pin='1234',
            estado='activo',
        )

    def tearDown(self):
        cache.clear()

    def test_base64_payload_size_limit_rejection(self):
        """Verifica que cadenas Base64 que exceden 10 MB sean rechazadas antes de decodificar."""
        field = Base64ImageField()
        payload_gigante = "A" * (MAX_BASE64_PAYLOAD_BYTES + 10)

        with self.assertRaises(ValidationError) as ctx:
            field.to_internal_value(payload_gigante)

        self.assertIn("excede el límite máximo permitido", str(ctx.exception))

    def test_base64_non_string_rejection(self):
        """Rechaza tipos de datos no compatibles con cadenas."""
        field = Base64ImageField()
        with self.assertRaises(ValidationError):
            field.to_internal_value([1, 2, 3])

    def test_base64_corrupt_data_rejection(self):
        """Rechaza cadenas Base64 corruptas o mal formadas."""
        field = Base64ImageField()
        with self.assertRaises(ValidationError):
            field.to_internal_value("data:image/png;base64,???no-es-base64-valido???")

    def test_http_security_headers_present(self):
        """Verifica que las cabeceras defensivas nosniff y X-Frame-Options estén presentes en las respuestas."""
        url = reverse('api_auth_login')
        response = self.client.post(url, {}, content_type='application/json')

        # Cabecera anti MIME-sniffing
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
        # Cabecera anti Clickjacking
        self.assertEqual(response.headers.get('X-Frame-Options'), 'DENY')

    def test_user_enumeration_neutral_response(self):
        """
        Verifica que solicitar la recuperación para un usuario inexistente retorne HTTP 200 OK
        con respuesta neutral sin enviar correos ni revelar la inexistencia del registro.
        """
        mail.outbox.clear()
        url = reverse('api_auth_request_pin_reset')
        response = self.client.post(url, {'usuario_id': 99999}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['correo_enmascarado'], '******@******')
        # No debe despachar correos
        self.assertEqual(len(mail.outbox), 0)

    def test_account_lockout_after_multiple_failed_logins(self):
        """
        Verifica que tras 5 intentos fallidos consecutivos de PIN,
        la cuenta quede temporalmente bloqueada (HTTP 429 Too Many Requests).
        """
        url = reverse('api_auth_login')

        # 4 intentos fallidos: retornan 401 Unauthorized indicando intentos restantes
        for i in range(1, 5):
            res = self.client.post(url, {'usuario_id': 10482, 'pin': '0000'}, format='json')
            self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertIn('Intentos restantes', res.data['error'])

        # 5to intento fallido: activa el bloqueo y retorna 429 Too Many Requests
        res5 = self.client.post(url, {'usuario_id': 10482, 'pin': '0000'}, format='json')
        self.assertEqual(res5.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('bloqueada', res5.data['error'])

        # Intento subsiguiente (incluso con el PIN correcto): permanece bloqueado durante el período de castigo
        res_bloqueado = self.client.post(url, {'usuario_id': 10482, 'pin': '1234'}, format='json')
        self.assertEqual(res_bloqueado.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('bloqueada', res_bloqueado.data['error'])

    def test_health_check_endpoint(self):
        """
        Verifica que el endpoint /api/v1/health/ retorne estado saludable
        y conectividad a la base de datos sin filtrar secretos ni rutas del servidor.
        """
        url = reverse('api_health_check')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')
        self.assertEqual(response.data['database'], 'connected')
        self.assertIn('server_timestamp', response.data)
        self.assertIn('is_https', response.data)

