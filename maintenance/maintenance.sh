#!/bin/bash

DB_HOST="${DB_HOST:-postgres-notifications}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-raijmobi_notifications_db}"
DB_USER="${DB_USER:-raijmobi_notifications}"
DB_PASSWORD="${DB_PASSWORD:-raijmobi_pass}"
LOG_DIR="${LOG_DIR:-/app/logs}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"

export PGPASSWORD="$DB_PASSWORD"

# NOVA FUNÇÃO: Aguarda o banco ficar 100% pronto antes de iniciar
echo "[$(date)] Verificando conexão com o banco ${DB_HOST}:${DB_PORT}..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q; then
        echo "[$(date)] Banco de dados está pronto!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT+1))
    echo "[$(date)] Banco não está pronto. Aguardando 5s... (Tentativa $RETRY_COUNT/$MAX_RETRIES)"
    sleep 5
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "[$(date)] ERRO: Banco de dados não ficou pronto após $(($MAX_RETRIES * 5)) segundos. Abortando."
    exit 1
fi

echo "[$(date)] Iniciando rotina de manutenção do banco ${DB_NAME}..."

# 1. VACUUM ANALYZE
echo "[$(date)] Executando VACUUM ANALYZE..."
if vacuumdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --analyze --verbose; then
    echo "[$(date)] VACUUM ANALYZE concluído com sucesso."
else
    echo "[$(date)] ERRO ao executar VACUUM ANALYZE"
fi

# 2. REINDEX CONCURRENTLY
echo "[$(date)] Executando REINDEX CONCURRENTLY..."
if reindexdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --concurrently --verbose; then
    echo "[$(date)] REINDEX CONCURRENTLY concluído com sucesso."
else
    echo "[$(date)] ERRO ao executar REINDEX CONCURRENTLY"
fi

# 3. LIMPEZA DE LOGS
if [ -d "$LOG_DIR" ]; then
    echo "[$(date)] Limpando logs com mais de ${LOG_RETENTION_DAYS} dias em ${LOG_DIR}..."
    find "$LOG_DIR" -type f -name "*.log" -mtime +$LOG_RETENTION_DAYS -delete
    echo "[$(date)] Limpeza de logs concluída."
else
    echo "[$(date)] Diretório de logs (${LOG_DIR}) não encontrado. Pulando limpeza de logs."
fi

echo "[$(date)] Rotina de manutenção concluída."