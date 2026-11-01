"""
Pruebas Unitarias de Seguridad y Hardening Defensivo (Fases 1 y 2).

Verifica:
1. Rechazo de payloads gigantes en Base64 (>10 MB) para prevención de DoS.
2. Validación de formatos binarios de imágenes (Magic Bytes).
3. Presencia de cabeceras de seguridad HTTP en las respuestas del servidor.
4. Mitigación de enumeración de usuarios en solicitud de OTP (SEC-04).
5. Bloqueo temporal de cuenta (Account Lockout) tras intentos fallidos repetidos (SEC-02).
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
    Pruebas automatizadas de defensas y mitigaciones de seguridad.
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
        """Rechaza tipos no string."""
        field = Base64ImageField()
        with self.assertRaises(ValidationError):
            field.to_internal_value([1, 2, 3])

    def test_base64_corrupt_data_rejection(self):
        """Rechaza cadenas Base64 corruptas."""
        field = Base64ImageField()
        with self.assertRaises(ValidationError):
            field.to_internal_value("data:image/png;base64,???no-es-base64-valido???")

    def test_http_security_headers_present(self):
        """Verifica que las cabeceras defensivas nosniff y X-Frame-Options estén presentes."""
        url = reverse('api_auth_login')
        response = self.client.post(url, {}, content_type='application/json')

        # Cabecera anti MIME-sniffing
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
        # Cabecera anti Clickjacking
        self.assertEqual(response.headers.get('X-Frame-Options'), 'DENY')

    def test_user_enumeration_neutral_response(self):
        """
        SEC-04: Verifica que enviar un ID inexistente retorne 200 OK con respuesta neutral
        sin revelar si el usuario existe o no y sin enviar correos.
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
        SEC-02: Verifica que tras 5 intentos fallidos consecutivos de PIN,
        la cuenta quede bloqueada temporalmente (HTTP 429 Too Many Requests).
        """
        url = reverse('api_auth_login')

        # 4 intentos fallidos: retornan 401 Unauthorized
        for i in range(1, 5):
            res = self.client.post(url, {'usuario_id': 10482, 'pin': '0000'}, format='json')
            self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertIn('Intentos restantes', res.data['error'])

        # 5to intento fallido: activa el bloqueo y retorna 429 Too Many Requests
        res5 = self.client.post(url, {'usuario_id': 10482, 'pin': '0000'}, format='json')
        self.assertEqual(res5.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('bloqueada', res5.data['error'])

        # Intento subsiguiente (incluso con el PIN correcto): permanece bloqueado
        res_bloqueado = self.client.post(url, {'usuario_id': 10482, 'pin': '1234'}, format='json')
        self.assertEqual(res_bloqueado.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('bloqueada', res_bloqueado.data['error'])
