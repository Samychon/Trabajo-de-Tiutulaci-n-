#!/bin/sh
set -e

if [ -z "$1" ]; then
  echo "Uso: restore.sh <ruta-al-archivo.dump>" >&2
  exit 1
fi

echo "[restore] Restaurando $1 sobre $PGDATABASE en $PGHOST..."
pg_restore -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" --clean --if-exists "$1"
echo "[restore] Restauracion completada."
