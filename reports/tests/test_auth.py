"""
Pruebas unitarias para el Portal de Autoservicio y Flujos de Recuperación de PIN vía OTP.
"""

from datetime import timedelta
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from reports.models import Usuario, CodigoVerificacion


class AuthPortalAndRecoveryTests(TestCase):
    """
    Verifica endpoints de verificación de trabajador, recuperación de PIN,
    despacho de correos OTP con plantilla y validación de códigos de seguridad.
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
        self.usuario_otro = Usuario.objects.create(
            usuario_id=48291,
            nombre='Carlos Mendoza',
            correo='carlos.mendoza@minera.cl',
            cargo='Supervisor de Turno',
            pin='4321',
            habilitar_sumario=False,
            estado='activo',
        )

    def test_auth_portal_web_renders_ok(self):
        """Verifica que el portal web /auth/portal/ renderice con 200 OK y su contenido HTML."""
        response = self.client.get('/auth/portal/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, 'Portal de Autoservicio')
        self.assertContains(response, 'Recuperar PIN')
        self.assertContains(response, 'Cambiar Correo')

    def test_verify_worker_success(self):
        """Verifica coincidencia exitosa de trabajador y correo corporativo."""
        url = reverse('api_auth_verify_worker')
        response = self.client.post(url, {
            'usuario_id': 10482,
            'correo': 'SEBASTIAN@minera.cl'  # Prueba case-insensitivity
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['valido'])
        self.assertEqual(response.data['usuario_id'], 10482)
        self.assertEqual(response.data['nombre'], 'Sebastián Arredondo')

    def test_verify_worker_invalid_email(self):
        """Falla si el correo no coincide con el registrado."""
        url = reverse('api_auth_verify_worker')
        response = self.client.post(url, {
            'usuario_id': 10482,
            'correo': 'otro@minera.cl'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['valido'])

    def test_pin_recovery_flow(self):
        """Verifica el restablecimiento de PIN y posterior login con la nueva clave."""
        url_recovery = reverse('api_auth_pin_recovery')
        response = self.client.post(url_recovery, {
            'usuario_id': 10482,
            'correo': 'sebastian@minera.cl',
            'nuevo_pin': '9999'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')

        # Verificar que el PIN cambió en la BD
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_pin('9999'))
        self.assertFalse(self.usuario.check_pin('1234'))

        # Probar login con el nuevo PIN
        url_login = reverse('api_auth_login')
        login_res = self.client.post(url_login, {'usuario_id': 10482, 'pin': '9999'}, format='json')
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertIn('token', login_res.data)

        # Login con PIN antiguo debe fallar
        login_old = self.client.post(url_login, {'usuario_id': 10482, 'pin': '1234'}, format='json')
        self.assertEqual(login_old.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pin_recovery_without_correo_and_alias(self):
        """Verifica cambio de PIN sin enviar correo (usando alias 'pin' o 'nuevo_pin')."""
        url_recovery = reverse('api_auth_pin_recovery')

        # Probar usando 'pin' como número entero y sin correo
        res1 = self.client.post(url_recovery, {
            'usuario_id': 10482,
            'pin': 5555
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.pin, '5555')
        self.assertTrue(self.usuario.check_pin('5555'))

        # Probar usando 'nuevo_pin' sin correo
        res2 = self.client.post(url_recovery, {
            'usuario_id': 10482,
            'nuevo_pin': '7777'
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.pin, '7777')

    def test_pin_recovery_invalid_pin_format(self):
        """Rechaza PINs que no tengan exactamente 4 dígitos numéricos."""
        url = reverse('api_auth_pin_recovery')
        # 3 dígitos
        res1 = self.client.post(url, {'usuario_id': 10482, 'correo': 'sebastian@minera.cl', 'nuevo_pin': '123'}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # 5 dígitos
        res2 = self.client.post(url, {'usuario_id': 10482, 'correo': 'sebastian@minera.cl', 'nuevo_pin': '12345'}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

        # Alfanumérico
        res3 = self.client.post(url, {'usuario_id': 10482, 'correo': 'sebastian@minera.cl', 'nuevo_pin': 'abcd'}, format='json')
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_email_success(self):
        """Verifica actualización de correo corporativo validando el PIN actual."""
        url = reverse('api_auth_change_email')
        response = self.client.post(url, {
            'usuario_id': 10482,
            'pin': '1234',
            'nuevo_correo': 's.arredondo@nuevodominio.cl'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.correo, 's.arredondo@nuevodominio.cl')

    def test_change_email_invalid_pin(self):
        """Falla si el PIN actual es incorrecto."""
        url = reverse('api_auth_change_email')
        response = self.client.post(url, {
            'usuario_id': 10482,
            'pin': '0000',
            'nuevo_correo': 'nuevo@minera.cl'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_email_duplicate_rejected(self):
        """Rechaza si el nuevo correo ya pertenece a otro trabajador activo."""
        url = reverse('api_auth_change_email')
        response = self.client.post(url, {
            'usuario_id': 10482,
            'pin': '1234',
            'nuevo_correo': 'carlos.mendoza@minera.cl'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_request_pin_reset_otp_email_sent(self):
        """Verifica generación de OTP y envío de correo para recuperación de PIN sin exigir correo manual."""
        mail.outbox.clear()
        url = reverse('api_auth_request_pin_reset')
        # Solo se envía usuario_id por seguridad
        response = self.client.post(url, {
            'usuario_id': 10482,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('correo_enmascarado', response.data)

        # Verificar que se envió un correo a la casilla registrada del usuario
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        self.assertIn(self.usuario.correo, sent_mail.to)
        self.assertIn('Report Seeker', sent_mail.subject)

        # Verificar que el código existe en BD
        otp = CodigoVerificacion.objects.filter(usuario=self.usuario, utilizado=False).first()
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp.codigo), 6)
        self.assertIn(otp.codigo, sent_mail.body)

    def test_verify_pin_reset_otp_success(self):
        """Verifica validación exitosa de código OTP y cambio de PIN."""
        # 1. Generar código sin ingresar correo
        url_req = reverse('api_auth_request_pin_reset')
        self.client.post(url_req, {'usuario_id': 10482}, format='json')
        otp = CodigoVerificacion.objects.filter(usuario=self.usuario, utilizado=False).first()

        # 2. Verificar código y establecer nuevo PIN
        url_verify = reverse('api_auth_verify_pin_reset')
        res_verify = self.client.post(url_verify, {
            'usuario_id': 10482,
            'codigo': otp.codigo,
            'nuevo_pin': '8888',
        }, format='json')

        self.assertEqual(res_verify.status_code, status.HTTP_200_OK)
        self.assertEqual(res_verify.data['status'], 'success')

        # Verificar PIN actualizado en BD
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.pin, '8888')
        self.assertTrue(self.usuario.check_pin('8888'))

        # Código debe estar marcado como utilizado
        otp.refresh_from_db()
        self.assertTrue(otp.utilizado)

        # Probar login con el nuevo PIN
        url_login = reverse('api_auth_login')
        res_login = self.client.post(url_login, {'usuario_id': 10482, 'pin': '8888'}, format='json')
        self.assertEqual(res_login.status_code, status.HTTP_200_OK)

    def test_verify_pin_reset_otp_invalid_code(self):
        """Verifica que un código incorrecto descuente intentos y sea rechazado."""
        url_req = reverse('api_auth_request_pin_reset')
        self.client.post(url_req, {'usuario_id': 10482}, format='json')
        otp = CodigoVerificacion.objects.filter(usuario=self.usuario, utilizado=False).first()

        url_verify = reverse('api_auth_verify_pin_reset')
        res_verify = self.client.post(url_verify, {
            'usuario_id': 10482,
            'codigo': '000000',  # Código incorrecto
            'nuevo_pin': '9999',
        }, format='json')

        self.assertEqual(res_verify.status_code, status.HTTP_400_BAD_REQUEST)
        otp.refresh_from_db()
        self.assertEqual(otp.intentos, 1)
        self.assertFalse(otp.utilizado)

    def test_verify_pin_reset_otp_expired_rejected(self):
        """Verifica rechazo de código OTP expirado."""
        otp = CodigoVerificacion.objects.create(
            usuario=self.usuario,
            correo='sebastian@minera.cl',
            codigo='654321',
            expira_en=timezone.now() - timedelta(minutes=1),  # Expirado
            utilizado=False,
        )

        url_verify = reverse('api_auth_verify_pin_reset')
        response = self.client.post(url_verify, {
            'usuario_id': 10482,
            'codigo': '654321',
            'nuevo_pin': '9999',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        otp.refresh_from_db()
        self.assertTrue(otp.utilizado)

