#!/bin/bash

# Intervalo padrão: 24 horas (86400 segundos)
MAINTENANCE_INTERVAL_SECONDS="${MAINTENANCE_INTERVAL_SECONDS:-86400}"

echo "Agendador de manutenção iniciado. Intervalo: ${MAINTENANCE_INTERVAL_SECONDS}s"

while true; do
    echo "[$(date)] Executando manutenção agendada..."
    /usr/local/bin/maintenance.sh
    echo "[$(date)] Próxima manutenção em ${MAINTENANCE_INTERVAL_SECONDS}s..."
    sleep "$MAINTENANCE_INTERVAL_SECONDS"
done