#!/bin/bash

echo "==> Aplicando migraciones..."
# La base puede tardar en aceptar conexiones: sin esto gunicorn arrancaría sin tablas.
intentos=0
until python manage.py migrate --noinput; do
    intentos=$((intentos + 1))
    if [ "$intentos" -ge 30 ]; then
        echo "==> No se pudo migrar la base de datos."
        exit 1
    fi
    echo "==> Base de datos no disponible, reintentando en 2s..."
    sleep 2
done

echo "==> Iniciando gunicorn en puerto 8000..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
