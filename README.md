# Report Seeker — Backend REST API

> **Evaluación Sumativa Unidad III (EVA2) — Programación de Aplicaciones**  
> Demostración de una API REST construida con Django y Django REST Framework.

---

## 1. Descripción del Proyecto y Continuidad con la EVA1

**Report Seeker** es una solución diseñada para la notificación, registro y auditoría de incidentes operacionales y condiciones de riesgo en faenas mineras subterráneas y a cielo abierto.

En la **EVA1**, el equipo desarrolló la interfaz móvil/frontend para captura de incidencias en terreno. En esta **EVA2**, este repositorio proporciona la infraestructura de **Backend** completa que da soporte a todos los requerimientos funcionales declarados:

- **Autenticación y Credenciales:** Control de acceso mediante credencial numérica de 5 dígitos y PIN de 4 dígitos, complementado con recuperación mediante código OTP por correo.
- **Catálogo de Sectores Mineros:** Registro y consulta de áreas físicas, frentes de extracción y túneles.
- **Gestión de Incidencias (CRUD):** Registro completo de reportes con fotografías adjuntas, niveles de prioridad (*Alta, Media, Baja*) y estados de ciclo de vida (*Capturado, En Revisión, Resuelto*).
- **Trazabilidad y Auditoría:** Bitácora inmutable de eventos para registrar cambios de estado y supervisión en faena.
- **Sincronización Offline:** Endpoints para sincronización atómica e idempotente (`push` y `pull`) compatibles con bases SQLite locales en dispositivos móviles.

---

## 2. Arquitectura Tecnológica

| Componente | Tecnología | Versión |
| :--- | :--- | :--- |
| **Lenguaje** | Python | 3.11+ |
| **Framework Backend** | Django | 6.1.2 |
| **Framework API REST** | Django REST Framework | 3.18.3 |
| **Bases de Datos Compatibles** | SQLite / MySQL & MariaDB | 8.4+ / PyMySQL 1.1+ |
| **Procesamiento de Imágenes** | Pillow | 13.0.0 |
| **CORS Middleware** | django-cors-headers | 4.9.0 |

---

## 3. Modelado de Datos y Relaciones

El backend se estructura sobre 5 entidades relacionales altamente normalizadas con integridad referencial:

1. **`Usuario`:** Personal operativo y supervisores de faena. Clave primaria numérica de 5 dígitos (`usuario_id`), nombre, cargo, correo único, PIN y estado laboral.
2. **`Localizacion`:** Catálogo de sectores y áreas físicas de trabajo minero (`nombre`, `activo`).
3. **`Reporte`:** Entidad central de incidencias. Relacionada mediante Foreign Key con:
   - `Usuario` (`on_delete=models.PROTECT`): Evita la pérdida de autoría en auditorías de seguridad.
   - `Localizacion` (`on_delete=models.SET_NULL`): Mantiene el histórico de reportes aunque un sector se desactive.
   - Contiene UUID universal, título, descripción, fotografía adjunta, fecha de captura, prioridad y estado.
4. **`ReporteHistorial`:** Bitácora inmutable para auditoría de cambios. Vinculada a `Reporte` (`CASCADE`) y `Usuario` (`PROTECT`), registrando campo modificado, valor anterior y nuevo valor.
5. **`CodigoVerificacion`:** Códigos OTP de 6 dígitos con vigencia temporal (15 min).

---

## 4. Catálogo de Endpoints y Demostración en Browsable API

Toda la funcionalidad del backend puede navegarse interactivamente desde la **Browsable API de Django REST Framework**:

| Endpoint | Método | Descripción | Permisos |
| :--- | :---: | :--- | :--- |
| `/api-auth/login/` | GET / POST | Inicio de sesión interactivo en la Browsable API | Público |
| `/api/v1/reportes/` | GET, POST | Listado paginado de reportes y creación | Lectura libre / Creación requiere login |
| `/api/v1/reportes/<id>/` | GET, PUT, PATCH, DELETE | Detalle, edición y eliminación de una incidencia | Solo autor o administrador (`is_staff`) |
| `/api/v1/localizaciones/` | GET, POST | Catálogo maestro de sectores mineros | Lectura libre / Escritura requiere login |
| `/api/v1/auth/login/` | POST | Login operativo móvil (usuario_id + PIN) emitiendo Token | Público (Rate-Limited) |
| `/api/v1/sync/pull/` | GET | Descarga delta incremental para SQLite móvil | Público / App móvil |
| `/api/v1/sync/push/` | POST | Subida atómica en lote de reportes offline | Público / App móvil |
| `/admin/` | GET, POST | Panel de control Django Admin para supervisores | Requiere rol `is_staff` |

---

## 5. Credenciales de Demostración

Para la evaluación en vivo se encuentran precargadas las siguientes cuentas de prueba:

- **Superusuario / Administrador (Django Admin y Browsable API):**
  - **Usuario:** `admin`
  - **Contraseña:** `admin1234`
- **Operarios Mineros (Autenticación operativa móvil y web):**
  - **Operario 1:** Credencial `10482` | PIN `1234` | Cargo: *Prevencionista de Riesgos*
  - **Operario 2:** Credencial `48291` | PIN `4321` | Cargo: *Supervisor de Turno Mina*
  - **Operario 3:** Credencial `73915` | PIN `5678` | Cargo: *Ingeniera de Seguridad Ocupacional*
