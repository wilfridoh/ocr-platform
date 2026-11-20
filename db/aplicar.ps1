<#
.SYNOPSIS
    Aplica schema.sql, seed.sql y vistas.sql contra una instancia SQL Server
    usando sqlcmd. Pensado para Windows / PowerShell.

.EXAMPLE
    .\aplicar.ps1 -Password 'Ocr_Dev_2026!'

.EXAMPLE
    .\aplicar.ps1 -Servidor 'localhost,14333' -Usuario sa -Password 'Ocr_Dev_2026!'
#>

param(
    [string]$Servidor = "localhost,1433",
    [string]$Usuario  = "sa",
    [Parameter(Mandatory = $true)]
    [string]$Password
)

$ErrorActionPreference = "Stop"

$sqlcmdPath = "sqlcmd"
if (-not (Get-Command sqlcmd -ErrorAction SilentlyContinue)) {
    $fallback = "C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn\SQLCMD.EXE"
    if (Test-Path $fallback) {
        $sqlcmdPath = $fallback
    } else {
        Write-Error "No se encontró sqlcmd en PATH ni en '$fallback'. Instala el ODBC Driver / Command Line Utilities."
        exit 1
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scripts = @("schema.sql", "schema_flujos_captura.sql", "seed.sql", "vistas.sql")

$falloGeneral = $false

foreach ($script in $scripts) {
    $ruta = Join-Path $scriptDir $script
    if (-not (Test-Path $ruta)) {
        Write-Error "No se encontró el script '$ruta'."
        $falloGeneral = $true
        continue
    }

    Write-Host ""
    Write-Host "==> Ejecutando $script contra $Servidor ..." -ForegroundColor Cyan

    & $sqlcmdPath -S $Servidor -U $Usuario -P $Password -C -b -I -f 65001 -i $ruta
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        Write-Error "El script '$script' terminó con código $exitCode."
        $falloGeneral = $true
    } else {
        Write-Host "<== $script aplicado correctamente." -ForegroundColor Green
    }
}

if ($falloGeneral) {
    Write-Error "Uno o más scripts fallaron. Revisa la salida anterior."
    exit 1
}

Write-Host ""
Write-Host "Todos los scripts se aplicaron correctamente." -ForegroundColor Green
exit 0
