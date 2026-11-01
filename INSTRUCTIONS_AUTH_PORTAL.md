# Especificación e Instrucciones de Implementación: Portal de Autoservicio y Endpoints de Autenticación
**Destinatario:** Agente Antigravity / Desarrollador Backend (`report_seeker_backend`)  
**Contexto del Proyecto:** Faena Minera Offline-First (Report Seeker)  
**Propósito:** Implementar la interfaz web (Portal de Autoservicio) y los endpoints REST para la recuperación/cambio de PIN y actualización de correo corporativo, manteniendo la identidad visual y estilo industrial de Report Seeker.

---

## 1. Resumen Ejecutivo y Necesidad Operativa

En operaciones mineras remotas (faenas sin acceso a internet público o en túneles subterráneos), la aplicación móvil `report_seeker` opera sin Firebase. La laptop del campamento/oficina técnica ejecuta el servidor central Django REST Framework en la red local (ej. `http://fedora.local:8000` o `http://192.168.114.199:8000`).

Para que los prevencionistas y operadores puedan:
1. **Recuperar o cambiar su PIN de 4 dígitos** cuando lo olviden o por seguridad.
2. **Actualizar su correo corporativo** sin depender de enlaces de confirmación en la nube pública.

Se requiere implementar en el repositorio `report_seeker_backend`:
- **Un Portal Web de Autoservicio (`/auth/portal/`)**: Página web responsiva (móvil y escritorio) servida directamente por Django, con tema oscuro (slate/navy/amber), animaciones fluidas y **cero dependencias de CDNs externas** (funciona 100% offline).
- **Endpoints REST API (`/api/v1/auth/...`)**: Consumidos tanto por la interfaz web como por la aplicación móvil React Native.

---

## 2. Identidad Visual y Especificaciones de Diseño

El portal web debe reproducir exactamente la identidad gráfica de Report Seeker:

| Token de Diseño | Valor HEX / CSS | Uso |
| :--- | :--- | :--- |
| **Canvas Background** | `#0A1118` / `#0D1722` | Fondo de página general (Deep Obsidian) |
| **Card Surface** | `#101E2E` / `#18283D` | Contenedores y tarjetas (Mining Slate) |
| **Border / Divider** | `#22384F` / `#2D4A6B` | Bordes sutiles de inputs y cards |
| **Primary Accent** | `#3B82F6` / `#2563EB` | Botones principales, enlaces de acción |
| **Mining Accent** | `#E5A93C` / `#F59E0B` | Badges industriales, iconos de advertencia |
| **Success Color** | `#10B981` | Checkmarks, mensajes de confirmación |
| **Danger / Error** | `#EF4444` | Alertas de error, validaciones fallidas |
| **Text Primary** | `#F8FAFC` | Títulos, textos destacados |
| **Text Secondary** | `#94A3B8` | Subtítulos, labels y placeholders |
| **Fonts** | `ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto` | Tipografía limpia y legible |

---

## 3. Endpoints REST API a Implementar

Todos los endpoints deben ubicarse bajo el prefijo `/api/v1/auth/` en la app `reports`.

### 3.1. `POST /api/v1/auth/verify-worker/`
Valida si un trabajador existe y su correo coincide, antes de permitirle cambiar el PIN.

- **Permisos:** `AllowAny`
- **Request Body (JSON):**
  ```json
  {
    "usuario_id": 10482,
    "correo": "s.arredondo@minera.cl"
  }
  ```
- **Respuesta Exitosa (200 OK):**
  ```json
  {
    "valido": true,
    "usuario_id": 10482,
    "nombre": "Sebastián Arredondo",
    "cargo": "Prevencionista de Riesgos"
  }
  ```
- **Respuesta Error (404 / 400):**
  ```json
  {
    "valido": false,
    "error": "El ID y correo no coinciden con ningún registro activo."
  }
  ```

---

### 3.2. `POST /api/v1/auth/pin-recovery/`
Permite a un trabajador (o supervisor) restablecer el PIN de acceso de 4 dígitos.

- **Permisos:** `AllowAny`
- **Request Body (JSON):**
  ```json
  {
    "usuario_id": 10482,
    "correo": "s.arredondo@minera.cl",
    "nuevo_pin": "5678"
  }
  ```
- **Validaciones:**
  - `usuario_id` debe ser un entero de 5 dígitos (10000 - 99999).
  - `correo` debe coincidir con el correo registrado en `Usuario.correo` (case-insensitive).
  - `nuevo_pin` debe ser una cadena numérica de exactamente 4 dígitos (`^\d{4}$`).
- **Acción:**
  - Ejecutar `usuario.set_pin(nuevo_pin)` y `usuario.save(update_fields=['pin', 'updated_at'])`.
  - Nota: al actualizar `updated_at`, el endpoint `GET /api/v1/sync/pull/` enviará el usuario actualizado a todos los dispositivos móviles en el próximo pull.
- **Respuesta Exitosa (200 OK):**
  ```json
  {
    "status": "success",
    "message": "PIN actualizado correctamente. Ya puedes ingresar con tu nueva clave en la app móvil.",
    "usuario_id": 10482
  }
  ```

---

### 3.3. `POST /api/v1/auth/change-email/`
Permite a un usuario autenticado por PIN actualizar su correo corporativo.

- **Permisos:** `AllowAny` (o `IsAuthenticated` si viene con Token)
- **Request Body (JSON):**
  ```json
  {
    "usuario_id": 10482,
    "pin": "5678",
    "nuevo_correo": "sebastian.arredondo@nuevodominio.cl"
  }
  ```
- **Validaciones:**
  - Validar que `usuario.check_pin(pin)` sea `True`.
  - Validar formato de `nuevo_correo`.
  - Validar que `nuevo_correo` no esté ya registrado por otro usuario activo (`Usuario.objects.filter(correo__iexact=nuevo_correo).exclude(usuario_id=usuario_id)`).
- **Acción:**
  - `usuario.correo = nuevo_correo`
  - `usuario.save(update_fields=['correo', 'updated_at'])`
  - Sincronizar también el modelo estándar `django.contrib.auth.models.User` si existe.
- **Respuesta Exitosa (200 OK):**
  ```json
  {
    "status": "success",
    "message": "Correo corporativo actualizado exitosamente.",
    "usuario_id": 10482,
    "correo": "sebastian.arredondo@nuevodominio.cl"
  }
  ```

---

## 4. Código Completo de Serializadores (`reports/serializers.py`)

Añadir al final de `reports/serializers.py`:

```python
import re
from rest_framework import serializers
from .models import Usuario


class VerifyWorkerSerializer(serializers.Serializer):
    usuario_id = serializers.IntegerField(min_value=10000, max_value=99999)
    correo = serializers.EmailField()

    def validate(self, attrs):
        usuario_id = attrs.get('usuario_id')
        correo = attrs.get('correo', '').strip().lower()

        try:
            usuario = Usuario.objects.get(usuario_id=usuario_id, estado='activo')
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({'usuario_id': 'No existe un usuario activo con esta credencial.'})

        if usuario.correo.strip().lower() != correo:
            raise serializers.ValidationError({'correo': 'El correo no coincide con el registrado en el sistema.'})

        attrs['usuario'] = usuario
        return attrs


class PinRecoverySerializer(serializers.Serializer):
    usuario_id = serializers.IntegerField(min_value=10000, max_value=99999)
    correo = serializers.EmailField()
    nuevo_pin = serializers.CharField(max_length=4, min_length=4)

    def validate_nuevo_pin(self, value):
        if not re.match(r'^\d{4}$', value):
            raise serializers.ValidationError('El PIN debe componerse exactamente de 4 dígitos numéricos.')
        return value

    def validate(self, attrs):
        usuario_id = attrs.get('usuario_id')
        correo = attrs.get('correo', '').strip().lower()

        try:
            usuario = Usuario.objects.get(usuario_id=usuario_id, estado='activo')
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({'usuario_id': 'No existe un usuario activo con este ID.'})

        if usuario.correo.strip().lower() != correo:
            raise serializers.ValidationError({'correo': 'El correo no corresponde al usuario indicado.'})

        attrs['usuario'] = usuario
        return attrs


class ChangeEmailSerializer(serializers.Serializer):
    usuario_id = serializers.IntegerField(min_value=10000, max_value=99999)
    pin = serializers.CharField(max_length=128)
    nuevo_correo = serializers.EmailField()

    def validate_nuevo_correo(self, value):
        correo = value.strip().lower()
        usuario_id = self.initial_data.get('usuario_id')
        if Usuario.objects.filter(correo__iexact=correo).exclude(usuario_id=usuario_id).exists():
            raise serializers.ValidationError('Este correo corporativo ya se encuentra asignado a otro usuario.')
        return correo

    def validate(self, attrs):
        usuario_id = attrs.get('usuario_id')
        raw_pin = attrs.get('pin')

        try:
            usuario = Usuario.objects.get(usuario_id=usuario_id, estado='activo')
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({'usuario_id': 'Credenciales no válidas.'})

        if not usuario.check_pin(raw_pin):
            raise serializers.ValidationError({'pin': 'El PIN actual ingresado es incorrecto.'})

        attrs['usuario'] = usuario
        return attrs
```

---

## 5. Código Completo de Vistas API y Portal Web (`reports/views.py`)

Añadir a `reports/views.py`:

```python
from django.shortcuts import render
from django.views.generic import View
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    VerifyWorkerSerializer,
    PinRecoverySerializer,
    ChangeEmailSerializer,
)


class VerifyWorkerView(APIView):
    """
    POST /api/v1/auth/verify-worker/
    Valida si el ID y correo corresponden a un usuario activo.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyWorkerSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'valido': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario = serializer.validated_data['usuario']
        return Response({
            'valido': True,
            'usuario_id': usuario.usuario_id,
            'nombre': usuario.nombre,
            'cargo': usuario.cargo,
        }, status=status.HTTP_200_OK)


class PinRecoveryView(APIView):
    """
    POST /api/v1/auth/pin-recovery/
    Restablece el PIN del usuario activo.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PinRecoverySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data['usuario']
        nuevo_pin = serializer.validated_data['nuevo_pin']

        usuario.set_pin(nuevo_pin)
        usuario.save(update_fields=['pin', 'updated_at'])

        return Response({
            'status': 'success',
            'message': 'PIN actualizado con éxito. Ya puedes ingresar en la app con tu nueva clave.',
            'usuario_id': usuario.usuario_id,
        }, status=status.HTTP_200_OK)


class ChangeEmailView(APIView):
    """
    POST /api/v1/auth/change-email/
    Actualiza el correo corporativo del usuario tras validar su PIN.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ChangeEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data['usuario']
        nuevo_correo = serializer.validated_data['nuevo_correo']

        usuario.correo = nuevo_correo
        usuario.save(update_fields=['correo', 'updated_at'])

        # Mantener sincronizado User de Django si existe
        User.objects.filter(username=str(usuario.usuario_id)).update(email=nuevo_correo)

        return Response({
            'status': 'success',
            'message': 'Correo corporativo actualizado exitosamente.',
            'usuario_id': usuario.usuario_id,
            'correo': nuevo_correo,
        }, status=status.HTTP_200_OK)


class AuthPortalWebView(View):
    """
    GET /auth/portal/
    Renderiza la interfaz web de autoservicio para recuperación de PIN y cambio de correo.
    """
    def get(self, request):
        return render(request, 'reports/auth_portal.html')
```

---

## 6. Configuración de Rutas (`reports/urls.py` y `config/urls.py`)

### En `reports/urls.py`:
```python
from django.urls import path
from .views import (
    LoginView,
    SyncPushView,
    SyncPullView,
    VerifyWorkerView,
    PinRecoveryView,
    ChangeEmailView,
)

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='api_auth_login'),
    path('auth/verify-worker/', VerifyWorkerView.as_view(), name='api_auth_verify_worker'),
    path('auth/pin-recovery/', PinRecoveryView.as_view(), name='api_auth_pin_recovery'),
    path('auth/change-email/', ChangeEmailView.as_view(), name='api_auth_change_email'),
    path('sync/push/', SyncPushView.as_view(), name='api_sync_push'),
    path('sync/pull/', SyncPullView.as_view(), name='api_sync_pull'),
]
```

### En `config/urls.py`:
Registrar la ruta de la vista web `/auth/portal/`:
```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from reports.views import AuthPortalWebView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/portal/', AuthPortalWebView.as_view(), name='auth_portal_web'),
    path('api/v1/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

---

## 7. Plantilla HTML del Portal Web (`reports/templates/reports/auth_portal.html`)

Crea la carpeta `reports/templates/reports/` si no existe y guarda el siguiente archivo `auth_portal.html`.
Contiene **CSS y JS embebidos** para no depender de CDNs (Bootstrap, Google Fonts, Tailwind CDN, etc.), garantizando que la página cargue instantáneamente y de forma 100% offline en la intranet minera.

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Portal de Autoservicio | Report Seeker</title>
  <style>
    :root {
      --bg-dark: #0A1118;
      --card-bg: #101E2E;
      --card-inner: #18283D;
      --border-color: #22384F;
      --border-active: #3B82F6;
      --primary: #3B82F6;
      --primary-hover: #2563EB;
      --amber: #E5A93C;
      --amber-light: rgba(229, 169, 60, 0.15);
      --success: #10B981;
      --success-light: rgba(16, 185, 129, 0.15);
      --danger: #EF4444;
      --danger-light: rgba(239, 68, 68, 0.15);
      --text-white: #F8FAFC;
      --text-muted: #94A3B8;
      --font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-dark);
      color: var(--text-white);
      font-family: var(--font-family);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 1.5rem 1rem;
      background-image: 
        radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 90% 80%, rgba(229, 169, 60, 0.05) 0%, transparent 40%);
    }

    .container {
      width: 100%;
      max-width: 480px;
    }

    /* Header del Portal */
    .brand-header {
      text-align: center;
      margin-bottom: 2rem;
    }

    .brand-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: var(--amber-light);
      border: 1px solid rgba(229, 169, 60, 0.35);
      color: var(--amber);
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      padding: 0.35rem 0.85rem;
      border-radius: 9999px;
      margin-bottom: 0.75rem;
    }

    .brand-badge svg {
      width: 14px;
      height: 14px;
      fill: currentColor;
    }

    .brand-title {
      font-size: 1.75rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      color: var(--text-white);
    }

    .brand-subtitle {
      font-size: 0.875rem;
      color: var(--text-muted);
      margin-top: 0.35rem;
    }

    /* Card Principal */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.4);
      overflow: hidden;
    }

    /* Tabs Segmentados */
    .tabs-nav {
      display: grid;
      grid-template-columns: 1fr 1fr;
      background: #0B1622;
      padding: 0.35rem;
      border-bottom: 1px solid var(--border-color);
      gap: 0.35rem;
    }

    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-family: inherit;
      font-size: 0.875rem;
      font-weight: 600;
      padding: 0.75rem 0.5rem;
      border-radius: 10px;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
    }

    .tab-btn:hover {
      color: var(--text-white);
      background: rgba(255, 255, 255, 0.03);
    }

    .tab-btn.active {
      background: var(--card-inner);
      color: var(--text-white);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border-color);
    }

    .tab-content {
      padding: 1.75rem 1.5rem;
    }

    .tab-pane {
      display: none;
    }

    .tab-pane.active {
      display: block;
      animation: fadeIn 0.25s ease-in-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Formularios y Campos */
    .form-group {
      margin-bottom: 1.25rem;
    }

    .form-label {
      display: block;
      font-size: 0.8125rem;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 0.4rem;
      text-transform: uppercase;
      letter-spacing: 0.025em;
    }

    .input-wrapper {
      position: relative;
    }

    .form-input {
      width: 100%;
      background: var(--card-inner);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      color: var(--text-white);
      font-family: inherit;
      font-size: 0.95rem;
      padding: 0.85rem 1rem;
      transition: all 0.2s ease;
      outline: none;
    }

    .form-input:focus {
      border-color: var(--border-active);
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
    }

    .pin-input {
      letter-spacing: 0.4em;
      font-size: 1.2rem;
      font-weight: 700;
      text-align: center;
    }

    .form-hint {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 0.35rem;
    }

    /* Botones */
    .btn {
      width: 100%;
      background: var(--primary);
      color: white;
      border: none;
      border-radius: 10px;
      font-family: inherit;
      font-size: 0.95rem;
      font-weight: 600;
      padding: 0.9rem 1.25rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      transition: all 0.2s ease;
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
      margin-top: 1rem;
    }

    .btn:hover:not(:disabled) {
      background: var(--primary-hover);
      transform: translateY(-1px);
    }

    .btn:disabled {
      opacity: 0.55;
      cursor: not-allowed;
      transform: none;
    }

    .btn-secondary {
      background: transparent;
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      box-shadow: none;
      margin-top: 0.5rem;
    }

    .btn-secondary:hover:not(:disabled) {
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-white);
    }

    /* Alertas y Feedback */
    .alert {
      padding: 0.85rem 1rem;
      border-radius: 10px;
      font-size: 0.875rem;
      line-height: 1.4;
      margin-bottom: 1.25rem;
      display: none;
      align-items: flex-start;
      gap: 0.6rem;
    }

    .alert.active {
      display: flex;
      animation: fadeIn 0.2s ease;
    }

    .alert-danger {
      background: var(--danger-light);
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #FCA5A5;
    }

    .alert-success {
      background: var(--success-light);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #6EE7B7;
    }

    .badge-info {
      background: rgba(59, 130, 246, 0.12);
      border: 1px solid rgba(59, 130, 246, 0.3);
      padding: 0.75rem 1rem;
      border-radius: 10px;
      margin-bottom: 1.25rem;
      font-size: 0.85rem;
      color: #BFDBFE;
    }

    .footer {
      text-align: center;
      margin-top: 2rem;
      font-size: 0.75rem;
      color: #64748B;
    }
  </style>
</head>
<body>

  <div class="container">
    <!-- Header -->
    <header class="brand-header">
      <div class="brand-badge">
        <svg viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
        Sistema Interno Faena
      </div>
      <h1 class="brand-title">Report Seeker</h1>
      <p class="brand-subtitle">Portal de Autoservicio de Credenciales y Perfil</p>
    </header>

    <!-- Card Principal -->
    <main class="card">
      <!-- Selector de Pestañas -->
      <nav class="tabs-nav" role="tablist">
        <button class="tab-btn active" id="tab-pin-btn" onclick="switchTab('pin')">
          🔑 Recuperar PIN
        </button>
        <button class="tab-btn" id="tab-email-btn" onclick="switchTab('email')">
          ✉️ Cambiar Correo
        </button>
      </nav>

      <div class="tab-content">
        <!-- Banner de Mensaje Global -->
        <div id="alert-banner" class="alert"></div>

        <!-- PESTAÑA 1: RECUPERAR PIN -->
        <section id="pane-pin" class="tab-pane active">
          <!-- Paso 1: Validación de Credenciales -->
          <form id="form-pin-step1" onsubmit="handleVerifyWorker(event)">
            <p class="form-hint" style="margin-bottom: 1.25rem; font-size: 0.85rem;">
              Ingresa tu ID de credencial (5 dígitos) y tu correo corporativo registrado para verificar tu identidad.
            </p>

            <div class="form-group">
              <label class="form-label" for="pin-worker-id">ID de Credencial (5 dígitos)</label>
              <input type="text" id="pin-worker-id" class="form-input" placeholder="Ej. 10482" maxlength="5" pattern="\d{5}" required inputmode="numeric">
            </div>

            <div class="form-group">
              <label class="form-label" for="pin-email">Correo Corporativo</label>
              <input type="email" id="pin-email" class="form-input" placeholder="ejemplo@minera.cl" required autocomplete="email">
            </div>

            <button type="submit" id="btn-pin-verify" class="btn">
              Verificar Identidad
            </button>
          </form>

          <!-- Paso 2: Establecer Nuevo PIN (Inicialmente oculto) -->
          <form id="form-pin-step2" style="display: none;" onsubmit="handleUpdatePin(event)">
            <div class="badge-info" id="verified-worker-badge">
              ✓ Identidad confirmada para: <strong id="verified-worker-name">Trabajador</strong>
            </div>

            <div class="form-group">
              <label class="form-label" for="new-pin">Nuevo PIN de Acceso (4 dígitos)</label>
              <input type="password" id="new-pin" class="form-input pin-input" maxlength="4" pattern="\d{4}" placeholder="••••" required inputmode="numeric">
              <p class="form-hint">Debe contener exactamente 4 números.</p>
            </div>

            <div class="form-group">
              <label class="form-label" for="confirm-pin">Confirma tu Nuevo PIN</label>
              <input type="password" id="confirm-pin" class="form-input pin-input" maxlength="4" pattern="\d{4}" placeholder="••••" required inputmode="numeric">
            </div>

            <button type="submit" id="btn-pin-submit" class="btn">
              Guardar Nuevo PIN
            </button>

            <button type="button" class="btn btn-secondary" onclick="resetPinFlow()">
              Volver atrás
            </button>
          </form>
        </section>

        <!-- PESTAÑA 2: CAMBIAR CORREO -->
        <section id="pane-email" class="tab-pane">
          <form id="form-change-email" onsubmit="handleChangeEmail(event)">
            <p class="form-hint" style="margin-bottom: 1.25rem; font-size: 0.85rem;">
              Actualiza tu correo corporativo confirmando tu ID y PIN de acceso actual.
            </p>

            <div class="form-group">
              <label class="form-label" for="email-worker-id">ID de Credencial (5 dígitos)</label>
              <input type="text" id="email-worker-id" class="form-input" placeholder="Ej. 10482" maxlength="5" pattern="\d{5}" required inputmode="numeric">
            </div>

            <div class="form-group">
              <label class="form-label" for="email-current-pin">PIN Actual (4 dígitos)</label>
              <input type="password" id="email-current-pin" class="form-input pin-input" maxlength="4" pattern="\d{4}" placeholder="••••" required inputmode="numeric">
            </div>

            <div class="form-group">
              <label class="form-label" for="new-corp-email">Nuevo Correo Corporativo</label>
              <input type="email" id="new-corp-email" class="form-input" placeholder="nuevo.correo@minera.cl" required>
            </div>

            <button type="submit" id="btn-email-submit" class="btn">
              Actualizar Correo
            </button>
          </form>
        </section>
      </div>
    </main>

    <!-- Footer -->
    <footer class="footer">
      Report Seeker &copy; 2026 &bull; Faena Minera Central Server &bull; Conexión Local Segura
    </footer>
  </div>

  <script>
    // Lógica interactiva del Portal Web
    let activeWorker = null;

    function showAlert(message, type = 'danger') {
      const banner = document.getElementById('alert-banner');
      banner.className = 'alert active alert-' + type;
      banner.innerHTML = (type === 'success' ? '✓ ' : '⚠ ') + message;
      banner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function hideAlert() {
      const banner = document.getElementById('alert-banner');
      banner.className = 'alert';
      banner.innerHTML = '';
    }

    function switchTab(tab) {
      hideAlert();
      document.getElementById('tab-pin-btn').classList.toggle('active', tab === 'pin');
      document.getElementById('tab-email-btn').classList.toggle('active', tab === 'email');
      document.getElementById('pane-pin').classList.toggle('active', tab === 'pin');
      document.getElementById('pane-email').classList.toggle('active', tab === 'email');
    }

    function resetPinFlow() {
      activeWorker = null;
      hideAlert();
      document.getElementById('form-pin-step1').style.display = 'block';
      document.getElementById('form-pin-step2').style.display = 'none';
      document.getElementById('new-pin').value = '';
      document.getElementById('confirm-pin').value = '';
    }

    // Paso 1: Verificar Trabajador
    async function handleVerifyWorker(event) {
      event.preventDefault();
      hideAlert();
      const workerId = document.getElementById('pin-worker-id').value.trim();
      const email = document.getElementById('pin-email').value.trim();
      const btn = document.getElementById('btn-pin-verify');

      btn.disabled = true;
      btn.innerText = 'Verificando...';

      try {
        const response = await fetch('/api/v1/auth/verify-worker/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ usuario_id: parseInt(workerId, 10), correo: email })
        });

        const data = await response.json();
        if (response.ok && data.valido) {
          activeWorker = { usuario_id: data.usuario_id, correo: email, nombre: data.nombre };
          document.getElementById('verified-worker-name').innerText = data.nombre + ' (' + data.cargo + ')';
          document.getElementById('form-pin-step1').style.display = 'none';
          document.getElementById('form-pin-step2').style.display = 'block';
        } else {
          const errMsg = data.error || (data.errors ? Object.values(data.errors).flat().join(' ') : 'Datos no válidos.');
          showAlert(errMsg, 'danger');
        }
      } catch (err) {
        showAlert('No se pudo comunicar con el servidor. Revisa tu conexión a la red local.', 'danger');
      } finally {
        btn.disabled = false;
        btn.innerText = 'Verificar Identidad';
      }
    }

    // Paso 2: Actualizar PIN
    async function handleUpdatePin(event) {
      event.preventDefault();
      hideAlert();

      if (!activeWorker) {
        showAlert('Sesión expirada. Vuelve a ingresar tu ID.', 'danger');
        resetPinFlow();
        return;
      }

      const newPin = document.getElementById('new-pin').value.trim();
      const confirmPin = document.getElementById('confirm-pin').value.trim();

      if (newPin.length !== 4 || !/^\d{4}$/.test(newPin)) {
        showAlert('El PIN debe tener exactamente 4 números.', 'danger');
        return;
      }

      if (newPin !== confirmPin) {
        showAlert('Los PINs ingresados no coinciden.', 'danger');
        return;
      }

      const btn = document.getElementById('btn-pin-submit');
      btn.disabled = true;
      btn.innerText = 'Guardando PIN...';

      try {
        const response = await fetch('/api/v1/auth/pin-recovery/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            usuario_id: activeWorker.usuario_id,
            correo: activeWorker.correo,
            nuevo_pin: newPin
          })
        });

        const data = await response.json();
        if (response.ok && data.status === 'success') {
          showAlert(data.message, 'success');
          resetPinFlow();
          document.getElementById('pin-worker-id').value = '';
          document.getElementById('pin-email').value = '';
        } else {
          const errMsg = data.message || (data.errors ? Object.values(data.errors).flat().join(' ') : 'Error al actualizar PIN.');
          showAlert(errMsg, 'danger');
        }
      } catch (err) {
        showAlert('Error de red al actualizar el PIN.', 'danger');
      } finally {
        btn.disabled = false;
        btn.innerText = 'Guardar Nuevo PIN';
      }
    }

    // Actualizar Correo Corporativo
    async function handleChangeEmail(event) {
      event.preventDefault();
      hideAlert();

      const workerId = document.getElementById('email-worker-id').value.trim();
      const currentPin = document.getElementById('email-current-pin').value.trim();
      const newEmail = document.getElementById('new-corp-email').value.trim();
      const btn = document.getElementById('btn-email-submit');

      btn.disabled = true;
      btn.innerText = 'Actualizando correo...';

      try {
        const response = await fetch('/api/v1/auth/change-email/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            usuario_id: parseInt(workerId, 10),
            pin: currentPin,
            nuevo_correo: newEmail
          })
        });

        const data = await response.json();
        if (response.ok && data.status === 'success') {
          showAlert(data.message, 'success');
          document.getElementById('email-worker-id').value = '';
          document.getElementById('email-current-pin').value = '';
          document.getElementById('new-corp-email').value = '';
        } else {
          const errMsg = (data.errors ? Object.values(data.errors).flat().join(' ') : (data.error || 'No se pudo actualizar el correo.'));
          showAlert(errMsg, 'danger');
        }
      } catch (err) {
        showAlert('Error de conexión al servidor central.', 'danger');
      } finally {
        btn.disabled = false;
        btn.innerText = 'Actualizar Correo';
      }
    }
  </script>
</body>
</html>
```

---

## 8. Verificación y Pruebas

Una vez implementado, ejecutar:

1. **Ejecutar Pruebas Automatizadas de Django:**
   ```bash
   python manage.py test reports
   ```
2. **Probar Endpoint con curl:**
   ```bash
   # 1. Verificar trabajador
   curl -X POST http://localhost:8000/api/v1/auth/verify-worker/ \
     -H "Content-Type: application/json" \
     -d '{"usuario_id": 10482, "correo": "s.arredondo@minera.cl"}'

   # 2. Restablecer PIN
   curl -X POST http://localhost:8000/api/v1/auth/pin-recovery/ \
     -H "Content-Type: application/json" \
     -d '{"usuario_id": 10482, "correo": "s.arredondo@minera.cl", "nuevo_pin": "5678"}'

   # 3. Iniciar sesión con nuevo PIN
   curl -X POST http://localhost:8000/api/v1/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"usuario_id": 10482, "pin": "5678"}'
   ```
3. **Probar Portal Web en Navegador:**
   - Abrir en navegador: `http://localhost:8000/auth/portal/` o `http://fedora.local:8000/auth/portal/`
   - Comprobar tanto en vista de escritorio como en emulador móvil (responsivo).
