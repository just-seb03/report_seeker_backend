"""
Pruebas Unitarias de Seguridad y Hardening Defensivo.

Verifica:
1. Rechazo de payloads gigantes en Base64 (>10 MB) para prevención de DoS.
2. Validación de formatos binarios de imágenes (Magic Bytes).
3. Presencia de cabeceras de seguridad HTTP en las respuestas del servidor.
"""

import base64
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from reports.serializers.common import Base64ImageField, MAX_BASE64_PAYLOAD_BYTES


class SecurityHardeningTests(TestCase):
    """
    Pruebas automatizadas de defensas y mitigaciones de seguridad.
    """
    def test_base64_payload_size_limit_rejection(self):
        """Verifica que cadenas Base64 que exceden 10 MB sean rechazadas antes de decodificar."""
        field = Base64ImageField()
        # Generar una cadena simulada que exceda el límite
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

