# Instrucciones de Implementación para el Frontend Móvil (Report Seeker)
**Destinatario:** Agente Antigravity / Desarrollador Móvil (`report_seeker`)  
**Contexto del Sistema:** App React Native / Expo (Offline-First con SQLite local) conectada a Servidor Central Django REST Framework en faena minera (`http://fedora.local:8000`).

---

## 1. Contexto y Diagnóstico

El backend central en Django ya está completamente operativo en la laptop de campamento/oficina técnica. Cuenta con:
1. Sincronización bidireccional (`/api/v1/sync/push/` y `/api/v1/sync/pull/`).
2. Portal web responsivo de autoservicio para cambio/recuperación de PIN y correo (`/auth/portal/`).
3. Endpoints REST de autenticación (`/api/v1/auth/login/`, `/api/v1/auth/verify-worker/`, `/api/v1/auth/pin-recovery/`, `/api/v1/auth/change-email/`).
4. Almacenamiento compatible de PINs de 4 dígitos en texto plano para validación offline en terreno.

Para que la experiencia en terreno sea 100% fluida, se requieren **3 cambios concretos en la aplicación móvil React Native**.

---

## 2. Resumen de Cambios a Realizar en el Frontend

| # | Área | Archivo(s) Típico(s) | Cambio Requerido |
| :--- | :--- | :--- | :--- |
| **1** | **Recuperación / Cambio de PIN** | `screens/LoginScreen.tsx` o `components/PinNumpad.tsx` | Añadir botón "¿Olvidaste o cambiaste tu PIN?" que abra el portal web local (`/auth/portal/`) o modal con llamada a `/pin-recovery/`, seguido de un `syncPull()` automático. |
| **2** | **Reportes Históricos para Prevencionista** | `services/syncService.ts` y `screens/ReportListScreen.tsx` | En `syncPull()`, insertar en SQLite todos los reportes devueltos por el backend. En la vista de lista, si el usuario tiene `habilitar_sumario: 1` (Prevencionista/Supervisor), mostrar **todos** los reportes de faena, no solo los propios. |
| **3** | **Descarga y Caché de Fotos en Pull** | `services/syncService.ts` | Al recibir `fotografia_url` en `syncPull()`, descargar la imagen a disco local con `FileSystem.downloadAsync` y guardar la ruta local en SQLite para visualización offline. |

---

## 3. Detalle de Implementación Paso a Paso

### Cambio 1: Acceso a Recuperación de PIN y Re-sincronización Inmediata

#### Problema
Si un trabajador cambia su PIN en el portal web (o lo restablece un supervisor), el teléfono móvil conserva el PIN anterior en su base de datos SQLite hasta que sincronice. Si el operador no puede ingresar, queda bloqueado offline.

#### Solución en Frontend
1. En la pantalla de login donde se ingresa el PIN, agregar un botón secundario: **"¿Olvidaste o cambiaste tu PIN?"**.
2. Al presionarlo, abrir el Portal de Autoservicio en el navegador del dispositivo usando `expo-web-browser` o `Linking`.
3. Al volver a la app (o con un botón "Actualizar credenciales"), ejecutar `syncPull()` para traer de inmediato el nuevo PIN desde el servidor Django.

#### Código de Ejemplo (`screens/LoginScreen.tsx`):
```typescript
import * as WebBrowser from 'expo-web-browser';
import { Button, Text, TouchableOpacity, View, Alert } from 'react-native';
import { syncPull } from '../services/syncService';

// URL base configurada (usa mDNS para evitar problemas de IP cambiante)
const SERVER_PORTAL_URL = 'http://fedora.local:8000/auth/portal/';

export const LoginScreen = () => {
  // ... lógica existente de Login y Numpad ...

  const handleOpenAuthPortal = async () => {
    try {
      // Abre el portal web responsivo servido por Django en la red local
      await WebBrowser.openBrowserAsync(SERVER_PORTAL_URL);
      
      // Al cerrar el navegador, sincronizamos para descargar el nuevo PIN en SQLite local
      const syncResult = await syncPull();
      if (syncResult.success) {
        Alert.alert('Sincronizado', 'Credenciales actualizadas. Ya puedes ingresar con tu nuevo PIN.');
      }
    } catch (error) {
      Alert.alert(
        'Aviso de Conexión',
        'Asegúrate de estar conectado a la red Wi-Fi de la faena para acceder al portal de credenciales.'
      );
    }
  };

  return (
    <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
      {/* ... Numpad e inputs existentes ... */}

      <TouchableOpacity onPress={handleOpenAuthPortal} style={{ marginTop: 24, padding: 12 }}>
        <Text style={{ color: '#E5A93C', fontWeight: '600', fontSize: 14 }}>
          🔑 ¿Olvidaste o cambiaste tu PIN?
        </Text>
      </TouchableOpacity>
    </View>
  );
};
```

---

### Cambio 2: Recepción y Visualización de Reportes Históricos (Especial para Prevencionista)

#### Problema Detectado
Al iniciar sesión como Prevencionista de Riesgos (ej. Sebastián Arredondo `10482`), la app no mostraba los reportes anteriores creados por otros trabajadores o en turnos previos.

#### Causa en Frontend
1. **En la inserción (`syncService.ts`)**: `syncPull()` recibía `data.reportes`, pero o no los persistía en SQLite, o ignoraba los reportes que no coincidían con el `usuario_id` actual.
2. **En la consulta de lista (`ReportListScreen.tsx`)**: La pantalla filtraba con `WHERE usuario_id = ?`, impidiendo que el prevencionista supervise incidencias globales de faena.

#### Solución en Frontend

##### A) Persistencia de Reportes en `syncService.ts`:
Asegurar que la función `syncPull()` procese el array `reportes` e inserte o actualice usando el `uuid` del reporte como clave:

```typescript
// En services/syncService.ts
export async function syncPull(): Promise<{ success: boolean; count: number }> {
  try {
    const response = await fetch('http://fedora.local:8000/api/v1/sync/pull/');
    if (!response.ok) throw new Error('Error al conectar con servidor Django');

    const data = await response.json();
    const { catalogos, reportes } = data;

    // 1. Actualizar catálogo de Usuarios en SQLite
    if (catalogos?.usuarios) {
      for (const u of catalogos.usuarios) {
        await db.runAsync(
          `INSERT OR REPLACE INTO usuarios 
           (usuario_id, nombre, correo, cargo, foto_perfil, pin, habilitar_sumario, estado, updated_at) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);`,
          [u.usuario_id, u.nombre, u.correo, u.cargo, u.foto_perfil, u.pin, u.habilitar_sumario ? 1 : 0, u.estado, u.updated_at]
        );
      }
    }

    // 2. Actualizar catálogo de Localizaciones en SQLite
    if (catalogos?.localizaciones) {
      for (const loc of catalogos.localizaciones) {
        await db.runAsync(
          `INSERT OR REPLACE INTO localizaciones (id, nombre, activo) VALUES (?, ?, 1);`,
          [loc.id, loc.nombre]
        );
      }
    }

    // 3. Persistir TODOS los reportes devueltos por el backend en SQLite
    let savedReportsCount = 0;
    if (reportes && Array.isArray(reportes)) {
      for (const r of reportes) {
        // Si el reporte ya existe localmente, actualiza campos; si no, inserta
        await db.runAsync(
          `INSERT INTO reportes (
            uuid, titulo, descripcion, fecha_captura, usuario_id, 
            usuario_nombre, usuario_cargo, ubicacion, ubicacion_id, 
            prioridad, estado, sincronizado, updated_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
          ON CONFLICT(uuid) DO UPDATE SET
            titulo = excluded.titulo,
            descripcion = excluded.descripcion,
            prioridad = excluded.prioridad,
            estado = excluded.estado,
            ubicacion = excluded.ubicacion,
            sincronizado = 1,
            updated_at = excluded.updated_at;`,
          [
            r.uuid, r.titulo, r.descripcion, r.fecha_captura, r.usuario_id,
            r.usuario_nombre, r.usuario_cargo, r.ubicacion, r.ubicacion_id,
            r.prioridad, r.estado, r.updated_at
          ]
        );
        savedReportsCount++;
      }
    }

    return { success: true, count: savedReportsCount };
  } catch (err) {
    console.warn('Fallo en syncPull:', err);
    return { success: false, count: 0 };
  }
}
```

##### B) Consulta según Rol de Usuario en `screens/ReportListScreen.tsx`:
El operador común solo ve sus reportes en terreno; pero el **Prevencionista** o **Supervisor** (`habilitar_sumario === 1` o `cargo.includes('Prevencionista')`) debe ver **todos los reportes**:

```typescript
// En hooks/useReports.ts o screens/ReportListScreen.tsx
export async function loadReports(currentUser: Usuario): Promise<Reporte[]> {
  // Si tiene permiso de sumario/gestión (Prevencionista), ve TODO el historial de faena
  const canViewAll = currentUser.habilitar_sumario === 1 || currentUser.habilitar_sumario === true;

  if (canViewAll) {
    return await db.getAllAsync<Reporte>(
      `SELECT * FROM reportes ORDER BY fecha_captura DESC;`
    );
  } else {
    // Operador estándar: solo sus propios reportes
    return await db.getAllAsync<Reporte>(
      `SELECT * FROM reportes WHERE usuario_id = ? ORDER BY fecha_captura DESC;`,
      [currentUser.usuario_id]
    );
  }
}
```

---

### Cambio 3: Descarga y Almacenamiento Local de Fotografías (`fotografia_url`)

#### Contexto
Cuando otro operador o el servidor crea un reporte con fotografía, el endpoint `/sync/pull/` retorna una URL absoluta:
`http://fedora.local:8000/media/reportes/2026/11/foto_a1b2c3d4.webp`.

Si el prevencionista abre el reporte sin conexión (en un túnel o sin cobertura Wi-Fi), la imagen no cargará si no fue guardada en caché local previamente.

#### Implementación en `syncService.ts`:
```typescript
import * as FileSystem from 'expo-file-system';

async function cacheReportPhoto(uuid: string, remoteUrl: string | null): Promise<string | null> {
  if (!remoteUrl) return null;

  try {
    const filename = remoteUrl.split('/').pop() || `foto_${uuid}.webp`;
    const localDir = `${FileSystem.documentDirectory}reportes/`;
    
    // Asegurar directorio
    const dirInfo = await FileSystem.getInfoAsync(localDir);
    if (!dirInfo.exists) {
      await FileSystem.makeDirectoryAsync(localDir, { intermediates: true });
    }

    const localUri = `${localDir}${filename}`;
    const fileInfo = await FileSystem.getInfoAsync(localUri);

    // Solo descargar si no existe localmente
    if (!fileInfo.exists) {
      const downloadResult = await FileSystem.downloadAsync(remoteUrl, localUri);
      return downloadResult.uri;
    }
    return localUri;
  } catch (e) {
    console.warn(`Error al cachear imagen del reporte ${uuid}:`, e);
    return remoteUrl; // Fallback a URL remota si falla
  }
}
```

---

## 4. Verificación de Integración Frontend <-> Backend

1. **Prueba de Login Offline con PIN Restaurado**:
   - Cambiar el PIN en el portal web (`/auth/portal/`) a `5678`.
   - Presionar "¿Olvidaste o cambiaste tu PIN?" en el móvil o ejecutar un `syncPull()`.
   - Desactivar Wi-Fi en el móvil (modo avión).
   - Ingresar PIN `5678`: El acceso debe ser concedido de inmediato sobre SQLite.
2. **Prueba de Vista de Prevencionista**:
   - Iniciar sesión con credencial `10482` (Sebastián Arredondo).
   - Realizar `syncPull()` conectado a `fedora.local:8000`.
   - Comprobar que en la pantalla de lista se visualizan todas las anomalías y reportes históricos de faena.

