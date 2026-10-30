#!/bin/sh
set -e

echo "=================================================================="
echo "🚀 ZERO-TOUCH N8N ORCHESTRATOR - CLOUD-AGNOSTIC BOOTSTRAP"
echo "=================================================================="

# 1. Dynamic Port Binding & Environment Variable Access inside Nodes
export N8N_PORT="${PORT:-${N8N_PORT:-5678}}"
export N8N_LISTEN_ADDRESS="0.0.0.0"
export N8N_BLOCK_ENV_ACCESS_IN_NODE="false"
export N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS="true"

# 2. Dynamic Memory Guard (Auto-detects Render Free vs Paid Server via DEPLOY_TARGET)
if [ "${DEPLOY_TARGET}" = "render_free" ]; then
    echo "⚙️  Mode: Render Free Tier (Applying 384MB V8 Heap Cap & Crash Guard)"
    export NODE_OPTIONS="--max-old-space-size=384"
else
    echo "⚙️  Mode: Dedicated/Paid Server (Applying High-Throughput V8 Heap)"
    export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=2048}"
fi

# 3. Verify Mandatory Encryption Key (Prevents Credential Loss on Container Crash)
if [ -z "${N8N_ENCRYPTION_KEY}" ]; then
    echo "❌ CRITICAL ERROR: N8N_ENCRYPTION_KEY is not set!"
    echo "Refusing to boot to prevent unrecoverable credential corruption."
    exit 1
fi

# 4. Wait & Retry Loop for External/Local PostgreSQL Readiness
if [ "${DB_TYPE}" = "postgresdb" ]; then
    echo "🔍 Verifying PostgreSQL connectivity at ${DB_POSTGRESDB_HOST}:${DB_POSTGRESDB_PORT:-5432}..."
    MAX_RETRIES=15
    COUNT=0
    until nc -z -w 5 "${DB_POSTGRESDB_HOST}" "${DB_POSTGRESDB_PORT:-5432}" 2>/dev/null || [ $COUNT -eq$MAX_RETRIES ]; do
        COUNT=$((COUNT + 1))
        echo "⏳ Waiting for PostgreSQL database... (Attempt ${COUNT}/${MAX_RETRIES})"
        sleep 3
    done
    if [ $COUNT -eq$MAX_RETRIES ]; then
        echo "⚠️  Warning: TCP pre-check timed out; handing connection retry to n8n core."
    else
        echo "✅ PostgreSQL TCP socket is reachable!"
    fi
fi

echo "✅ Launching n8n on ${N8N_LISTEN_ADDRESS}:${N8N_PORT} (Timezone:${GENERIC_TIMEZONE:-Asia/Kolkata})"
exec /docker-entrypoint.sh