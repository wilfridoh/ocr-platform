#!/usr/bin/env bash
# ============================================================================
# OCR Platform — aplicar.sh
# Equivalente a aplicar.ps1 para Linux. Lo usa el contenedor db-init de
# docker-compose (espera a que SQL Server arranque y ejecuta las migraciones).
#
# sqlcmd se espera en /opt/mssql-tools18/bin/sqlcmd (imagen con
# mssql-tools18), o en PATH.
#
# Uso:
#   ./aplicar.sh [-S servidor] [-U usuario] -P password
#
# Variables de entorno equivalentes: DB_SERVIDOR, DB_USUARIO, DB_PASSWORD
# ============================================================================
set -euo pipefail

SERVIDOR="${DB_SERVIDOR:-localhost,1433}"
USUARIO="${DB_USUARIO:-sa}"
PASSWORD="${DB_PASSWORD:-}"

while getopts "S:U:P:" opt; do
    case "$opt" in
        S) SERVIDOR="$OPTARG" ;;
        U) USUARIO="$OPTARG" ;;
        P) PASSWORD="$OPTARG" ;;
        *)
            echo "Uso: $0 [-S servidor] [-U usuario] -P password" >&2
            exit 1
            ;;
    esac
done

if [[ -z "$PASSWORD" ]]; then
    echo "ERROR: falta la contraseña (usa -P o la variable DB_PASSWORD)." >&2
    exit 1
fi

SQLCMD="sqlcmd"
if ! command -v sqlcmd >/dev/null 2>&1; then
    if [[ -x "/opt/mssql-tools18/bin/sqlcmd" ]]; then
        SQLCMD="/opt/mssql-tools18/bin/sqlcmd"
    elif [[ -x "/opt/mssql-tools/bin/sqlcmd" ]]; then
        SQLCMD="/opt/mssql-tools/bin/sqlcmd"
    else
        echo "ERROR: no se encontró sqlcmd en PATH ni en /opt/mssql-tools18/bin ni /opt/mssql-tools/bin." >&2
        exit 1
    fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS=("schema.sql" "schema_flujos_captura.sql" "seed.sql" "vistas.sql")

fallo_general=0

for script in "${SCRIPTS[@]}"; do
    ruta="$SCRIPT_DIR/$script"
    if [[ ! -f "$ruta" ]]; then
        echo "ERROR: no se encontró el script '$ruta'." >&2
        fallo_general=1
        continue
    fi

    echo ""
    echo "==> Ejecutando $script contra $SERVIDOR ..."

    if "$SQLCMD" -S "$SERVIDOR" -U "$USUARIO" -P "$PASSWORD" -C -b -I -f 65001 -i "$ruta"; then
        echo "<== $script aplicado correctamente."
    else
        codigo=$?
        echo "ERROR: el script '$script' terminó con código $codigo." >&2
        fallo_general=1
    fi
done

if [[ "$fallo_general" -ne 0 ]]; then
    echo "Uno o más scripts fallaron. Revisa la salida anterior." >&2
    exit 1
fi

echo ""
echo "Todos los scripts se aplicaron correctamente."
exit 0
