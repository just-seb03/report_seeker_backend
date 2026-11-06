"""
Servicio de Sincronización Bidireccional Offline-First.

Este módulo implementa el protocolo de sincronización entre los dispositivos
móviles de faena y el servidor central:
1. `procesar_push_sincronizacion`: Recepción atómica e idempotente de lotes de reportes
   y eventos de auditoría (historial). Resuelve referencias lógicas, guarda imágenes
   y previene colisiones.
2. `obtener_conjuntos_pull`: Consulta incremental (delta) basada en timestamp
   `since` para catálogos de localizaciones, usuarios autorizados y reportes recientes.

Dónde se utiliza:
- En `reports/views/sync_views.py` (`SyncPushView` y `SyncPullView`) para procesar
  las llamadas de sincronización realizadas por `SyncService.ts` de la aplicación móvil.
- En las pruebas de sincronización offline: `reports/tests/test_sync.py`.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from reports.models import Usuario, Localizacion, Reporte, ReporteHistorial

logger = logging.getLogger(__name__)


def procesar_push_sincronizacion(reportes_data: List[Dict[str, Any]], historial_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Procesa un lote de sincronización ascendente (móvil -> servidor).

    Garantiza idempotencia total utilizando UUID v4 generado en el dispositivo cliente.
    Si un reporte o evento de historial ya existe en la base de datos central, se actualiza
    sin duplicar información ni fallar la transacción.

    Args:
        reportes_data (List[Dict[str, Any]]): Lista de reportes serializados.
        historial_data (List[Dict[str, Any]]): Lista de eventos de bitácora/auditoría.

    Returns:
        Dict[str, Any]: Diccionario con la lista de identificadores sincronizados (`synced_reports`, `synced_historial`).
    """
    synced_reports = []
    synced_historial = []

    with transaction.atomic():
        # -------------------------------------------------------------
        # 1. Sincronización de Incidencias / Reportes
        # -------------------------------------------------------------
        for rep in reportes_data:
            rep_uuid = rep['uuid']
            local_id = rep.get('local_id')

            # Resolver relaciones de clave foránea de forma tolerante a fallos
            usuario = None
            if rep.get('usuario_id'):
                usuario = Usuario.objects.filter(usuario_id=rep['usuario_id']).first()

            localizacion = None
            if rep.get('ubicacion_id'):
                localizacion = Localizacion.objects.filter(id=rep['ubicacion_id']).first()
            elif rep.get('ubicacion'):
                localizacion = Localizacion.objects.filter(nombre=rep['ubicacion']).first()

            valores_defecto = {
                'titulo': rep['titulo'],
                'descripcion': rep.get('descripcion') or '',
                'fecha_captura': rep['fecha_captura'],
                'usuario': usuario,
                'usuario_nombre': rep.get('usuario_nombre') or (usuario.nombre if usuario else ''),
                'usuario_cargo': rep.get('usuario_cargo') or (usuario.cargo if usuario else ''),
                'localizacion': localizacion,
                'ubicacion_texto': rep.get('ubicacion') or (localizacion.nombre if localizacion else ''),
                'prioridad': rep.get('prioridad', 'Media'),
                'estado': rep.get('estado', 'capturado'),
            }

            reporte_obj, _ = Reporte.objects.update_or_create(
                uuid=rep_uuid,
                defaults=valores_defecto
            )

            # Si se adjuntó una fotografía en Base64, asignarla y persistir en disco
            foto_archivo = rep.get('fotografia_base64')
            if foto_archivo:
                reporte_obj.fotografia = foto_archivo
                reporte_obj.save(update_fields=['fotografia'])

            synced_reports.append({
                'local_id': local_id,
                'uuid': str(rep_uuid),
                'status': 'sincronizado'
            })

        # -------------------------------------------------------------
        # 2. Sincronización de Auditoría / Historial de Cambios
        # -------------------------------------------------------------
        for hist in historial_data:
            hist_uuid = hist['uuid']
            local_id = hist.get('local_id')
            rep_uuid = hist['reporte_uuid']

            reporte_obj = Reporte.objects.filter(uuid=rep_uuid).first()
            if not reporte_obj:
                # Si el reporte padre no existe, omitir para no romper el lote completo
                logger.warning(f"Historial huérfano omitido: reporte UUID {rep_uuid} no encontrado.")
                continue

            usuario = None
            if hist.get('usuario_id'):
                usuario = Usuario.objects.filter(usuario_id=hist['usuario_id']).first()

            hist_defaults = {
                'reporte': reporte_obj,
                'usuario': usuario,
                'usuario_nombre': hist.get('usuario_nombre') or (usuario.nombre if usuario else 'Usuario'),
                'campo_modificado': hist['campo_modificado'],
                'valor_anterior': hist.get('valor_anterior'),
                'valor_nuevo': hist.get('valor_nuevo') or '',
                'fecha_cambio': hist['fecha_cambio'],
            }

            ReporteHistorial.objects.update_or_create(
                uuid=hist_uuid,
                defaults=hist_defaults
            )

            synced_historial.append({
                'local_id': local_id,
                'uuid': str(hist_uuid),
                'status': 'sincronizado'
            })

    return {
        'status': 'success',
        'synced_reports': synced_reports,
        'synced_historial': synced_historial,
    }


def obtener_conjuntos_pull(since_dt: Optional[datetime] = None):
    """
    Obtiene los querysets filtrados para la sincronización pull.
    Si se proporciona `since_dt`, devuelve solo registros modificados a partir de esa fecha.
    En caso contrario, retorna el catálogo base inicial.

    Args:
        since_dt (Optional[datetime]): Timestamp de la última sincronización del móvil.

    Returns:
        Tuple: (localizaciones_qs, usuarios_qs, reportes_qs, server_timestamp)
    """
    ahora = timezone.now()

    if since_dt:
        locs_qs = Localizacion.objects.filter(updated_at__gte=since_dt, activo=True)
        users_qs = Usuario.objects.filter(updated_at__gte=since_dt)
        reportes_qs = Reporte.objects.filter(updated_at__gte=since_dt).order_by('-fecha_captura')
    else:
        locs_qs = Localizacion.objects.filter(activo=True)
        users_qs = Usuario.objects.filter(estado='activo')
        reportes_qs = Reporte.objects.all().order_by('-fecha_captura')[:100]

    return locs_qs, users_qs, reportes_qs, ahora

