<#
.SYNOPSIS
  Detiene y elimina los contenedores de la plataforma OCR.

.DESCRIPTION
  Por defecto conserva los volumenes (datos de SQL Server y archivos subidos).
  Con -BorrarDatos elimina tambien los volumenes (equivale a empezar de cero).

.EXAMPLE
  .\scripts\bajar.ps1
  .\scripts\bajar.ps1 -BorrarDatos
#>
[CmdletBinding()]
param(
    [switch]$BorrarDatos
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

if ($BorrarDatos) {
    $resp = Read-Host "Se borraran TODOS los datos (BD y archivos). Escribe SI para continuar"
    if ($resp -ne "SI") { Write-Host "Cancelado."; exit 0 }
    docker compose down -v --remove-orphans
} else {
    docker compose down --remove-orphans
}

if ($?) { Write-Host "Plataforma detenida." -ForegroundColor Green } else { exit 1 }
