"""
Servicio de Autenticación y Recuperación de PIN vía OTP (One-Time Password).

Este módulo encapsula toda la lógica de negocio correspondiente al ciclo de vida
de los códigos de seguridad de un solo uso (OTP):
1. Generación criptográfica segura de códigos de 6 dígitos mediante CSPRNG.
2. Despacho transaccional de correos electrónicos en formato HTML responsive y texto plano.
3. Validación y consumo de códigos con protección anti-fuerza bruta.
4. Actualización sincronizada del PIN tanto en el modelo de dominio (Usuario)
   como en el subsistema de autenticación de Django (auth.User).

Dónde se utiliza:
- En `reports/views/auth_views.py` (`RequestPinResetView` y `VerifyPinResetView`) para procesar
  la solicitud y verificación de códigos OTP solicitados desde la app móvil o el portal web.
- En las pruebas de recuperación de contraseña: `reports/tests/test_auth.py` y `reports/tests/test_security.py`.
"""

import datetime
import logging
import secrets
from typing import Tuple
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from reports.models import Usuario, CodigoVerificacion

logger = logging.getLogger(__name__)


def enmascarar_correo(correo: str) -> str:
    """
    Ofusca una dirección de correo para despliegue seguro en interfaces públicas.
    
    Ejemplo:
        'sebastian@minera.cl' -> 's***n@minera.cl'
        'ab@minera.cl'        -> 'a*@minera.cl'

    Args:
        correo (str): Dirección de correo completa del usuario.

    Returns:
        str: Cadena enmascarada conservando el dominio y los caracteres extremos.
    """
    if not correo or '@' not in correo:
        return correo

    usuario_parte, dominio_parte = correo.split('@', 1)
    if len(usuario_parte) <= 2:
        usuario_enmascarado = usuario_parte[0] + '*'
    else:
        usuario_enmascarado = usuario_parte[0] + '***' + usuario_parte[-1]

    return f"{usuario_enmascarado}@{dominio_parte}"


def generar_codigo_numerico(longitud: int = 6) -> str:
    """
    Genera una secuencia numérica criptográficamente segura para códigos OTP.
    
    Utiliza el módulo `secrets` del sistema operativo (CSPRNG) para evitar
    vulnerabilidades de entropía presentes en generadores pseudoaleatorios estándar.

    Args:
        longitud (int): Cantidad de dígitos (por defecto 6).

    Returns:
        str: Código de 6 dígitos entre 100000 y 999999.
    """
    min_val = 10 ** (longitud - 1)
    max_val = (10 ** longitud) - 1
    rango = max_val - min_val + 1
    return str(min_val + secrets.randbelow(rango))


def solicitar_codigo_recuperacion(usuario: Usuario, duracion_minutos: int = 15) -> Tuple[CodigoVerificacion, str]:
    """
    Inicia el flujo de recuperación de PIN para un usuario activo:
    1. Invalida de forma preventiva los códigos previos no utilizados.
    2. Genera un nuevo código OTP seguro de 6 dígitos.
    3. Persiste el registro en la base de datos con tiempo de expiración.
    4. Envía el correo electrónico con plantilla HTML corporativa.

    Args:
        usuario (Usuario): Instancia del trabajador solicitante.
        duracion_minutos (int): Ventana de validez del código (por defecto 15 min).

    Returns:
        Tuple[CodigoVerificacion, str]: Tupla con el objeto persistido y el código generado.

    Raises:
        Exception: Si ocurre un fallo en el transporte SMTP de correo.
    """
    # 1. Invalidar códigos previos pendientes
    usuario.codigos_verificacion.filter(utilizado=False).update(utilizado=True)

    # 2. Generar código y fecha límite
    codigo = generar_codigo_numerico(6)
    expira_en = timezone.now() + datetime.timedelta(minutes=duracion_minutos)

    # 3. Guardar en base de datos
    otp_obj = CodigoVerificacion.objects.create(
        usuario=usuario,
        correo=usuario.correo,
        codigo=codigo,
        expira_en=expira_en,
    )

    # 4. Enviar correo electrónico
    enviar_correo_otp(usuario, codigo, duracion_minutos)

    return otp_obj, codigo


def enviar_correo_otp(usuario: Usuario, codigo: str, minutos_validez: int = 15) -> None:
    """
    Construye y envía el correo electrónico con el código OTP tanto en versión
    texto plano como en plantilla HTML responsive con diseño corporativo minero.

    Args:
        usuario (Usuario): Destinatario del correo.
        codigo (str): Código numérico de 6 dígitos.
        minutos_validez (int): Tiempo de vigencia informado al usuario.

    Raises:
        Exception: Si el servidor SMTP rechaza el envío o no hay conexión de red.
    """
    asunto = f"Report Seeker - Código de Seguridad: {codigo}"
    remitente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Report Seeker <noreply@minera.cl>')

    mensaje_texto = (
        f"Hola, {usuario.nombre}:\n\n"
        f"Has solicitado restablecer tu PIN de acceso para Report Seeker en Faena Minera.\n\n"
        f"Tu código de seguridad de 6 dígitos es:\n"
        f"--> {codigo} <--\n\n"
        f"Este código es válido por {minutos_validez} minutos.\n"
        f"Si no realizaste esta solicitud, puedes ignorar este mensaje.\n"
    )

    mensaje_html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <title>Recuperación de PIN</title>
    </head>
    <body style="margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0A1118; color: #F8FAFC;">
      <div style="max-width: 500px; margin: 0 auto; background-color: #101E2E; border: 1px solid #22384F; border-radius: 14px; padding: 28px; box-shadow: 0 8px 24px rgba(0,0,0,0.5);">
        <div style="text-align: center; margin-bottom: 24px;">
          <span style="background: rgba(229,169,60,0.15); border: 1px solid rgba(229,169,60,0.3); color: #E5A93C; font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; padding: 4px 10px; border-radius: 20px;">
            Report Seeker &bull; Faena Minera
          </span>
          <h2 style="color: #F8FAFC; margin: 14px 0 4px 0; font-size: 20px;">Recuperación de PIN de Acceso</h2>
          <p style="color: #94A3B8; font-size: 13px; margin: 0;">Servidor Central de Operaciones</p>
        </div>
        
        <p style="font-size: 14px; line-height: 1.5; color: #E2E8F0;">
          Hola, <strong>{usuario.nombre}</strong> ({usuario.cargo}):
        </p>
        <p style="font-size: 14px; line-height: 1.5; color: #94A3B8;">
          Ingresa el siguiente código de 6 dígitos en la aplicación móvil o en el portal web para restablecer tu clave de 4 dígitos:
        </p>

        <div style="background-color: #18283D; border: 2px dashed #3B82F6; border-radius: 10px; padding: 20px; text-align: center; margin: 24px 0;">
          <span style="font-size: 34px; font-weight: 800; letter-spacing: 10px; color: #3B82F6; font-family: monospace;">{codigo}</span>
        </div>

        <p style="font-size: 13px; color: #94A3B8; line-height: 1.4;">
          ⏱ <strong>Válido por {minutos_validez} minutos</strong> &bull; Uso único.<br>
          🔒 Por seguridad, nunca compartas este código con terceros.
        </p>
        
        <hr style="border: none; border-top: 1px solid #22384F; margin: 24px 0;">
        
        <p style="font-size: 11px; color: #64748B; text-align: center; margin: 0;">
          Si tú no solicitaste este código, tu cuenta permanece segura y puedes desestimar este correo.
        </p>
      </div>
    </body>
    </html>
    """

    send_mail(
        subject=asunto,
        message=mensaje_texto,
        from_email=remitente,
        recipient_list=[usuario.correo],
        html_message=mensaje_html,
        fail_silently=False,
    )
    logger.info(f"Correo OTP despachado exitosamente a {usuario.correo} para usuario #{usuario.usuario_id}")


def aplicar_cambio_pin(usuario: Usuario, otp_obj: CodigoVerificacion, nuevo_pin: str) -> None:
    """
    Ejecuta el cambio de PIN de un usuario validado por OTP:
    1. Marca el código de verificación como utilizado para prevenir reutilizaciones.
    2. Actualiza el PIN del usuario en texto plano (necesario para validación offline en móvil).
    3. Actualiza el password del usuario interno Django (para tokens de API).

    Args:
        usuario (Usuario): Usuario a modificar.
        otp_obj (CodigoVerificacion): Registro de verificación validado.
        nuevo_pin (str): Nueva contraseña numérica de 4 dígitos.
    """
    pin_limpio = str(nuevo_pin).strip()

    # 1. Consumir código
    otp_obj.utilizado = True
    otp_obj.save(update_fields=['utilizado'])

    # 2. Actualizar PIN del usuario operativo
    usuario.set_pin(pin_limpio)
    usuario.save(update_fields=['pin', 'updated_at'])

    # 3. Sincronizar cuenta interna Django
    django_user, _ = User.objects.get_or_create(
        username=str(usuario.usuario_id),
        defaults={'first_name': usuario.nombre, 'email': usuario.correo}
    )
    django_user.set_password(pin_limpio)
    django_user.save()

    logger.info(f"PIN actualizado exitosamente para usuario #{usuario.usuario_id}")

