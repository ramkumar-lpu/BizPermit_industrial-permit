#!/bin/sh
set -e

# ==============================================================================
# Supabase Kong Safe Declarative Config Entrypoint
# ==============================================================================
# kong.yml uses DB-less mode (declarative configuration). Kong does not natively
# perform environment variable interpolation on startup.
# This script safely substitutes SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY
# into /home/kong/kong.yml using sed, without using eval or shell echo expansion,
# ensuring all YAML quoting (e.g., _format_version: "2.1") is preserved intact.
# ==============================================================================

TEMPLATE_PATH="${KONG_CONFIG_TEMPLATE:-/home/kong/temp.yml}"
TARGET_PATH="${KONG_DECLARATIVE_CONFIG:-/home/kong/kong.yml}"

if [ ! -f "$TEMPLATE_PATH" ]; then
    echo "[kong-entrypoint] Error: Template file $TEMPLATE_PATH not found." >&2
    exit 1
fi

echo "[kong-entrypoint] Interpolating keys into $TARGET_PATH..."
sed \
    -e "s|\${SUPABASE_ANON_KEY}|${SUPABASE_ANON_KEY}|g" \
    -e "s|\${SUPABASE_SERVICE_ROLE_KEY}|${SUPABASE_SERVICE_ROLE_KEY}|g" \
    "$TEMPLATE_PATH" > "$TARGET_PATH"

echo "[kong-entrypoint] Declarative configuration ready. Starting Kong..."
exec /docker-entrypoint.sh kong docker-start "$@"
