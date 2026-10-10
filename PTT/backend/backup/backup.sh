#!/bin/sh
set -e

BACKUP_DIR="/backups"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"

mkdir -p "$BACKUP_DIR"

echo "[backup] Servicio de respaldo iniciado. Intervalo: ${INTERVAL_SECONDS}s, retencion: ${RETENTION_DAYS} dias"

while true; do
  timestamp=$(date +%Y%m%d_%H%M%S)
  file="$BACKUP_DIR/ipi2_inventario_${timestamp}.dump"

  echo "[backup] Generando respaldo: $file"
  if pg_dump -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -F c -f "$file"; then
    echo "[backup] Respaldo completado."
  else
    echo "[backup] ERROR generando respaldo" >&2
  fi

  # Retencion local; para cumplir 3-2-1 hay que copiar ademas este directorio fuera del host (ver README de la carpeta).
  find "$BACKUP_DIR" -name "*.dump" -mtime +"$RETENTION_DAYS" -delete

  sleep "$INTERVAL_SECONDS"
done
