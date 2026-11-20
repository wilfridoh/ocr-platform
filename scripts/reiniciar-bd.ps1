<#
.SYNOPSIS
  Recrea la base de datos desde cero: baja todo, borra el volumen de SQL Server
  y vuelve a levantar (db-init aplica de nuevo schema/seed/vistas).

.DESCRIPTION
  Los archivos subidos (volumen archivos-data) se conservan salvo que se pase -BorrarArchivos.

.EXAMPLE
  .\scripts\reiniciar-bd.ps1
  .\scripts\reiniciar-bd.ps1 -BorrarArchivos
  .\scripts\reiniciar-bd.ps1 -Forzar     # sin pedir confirmacion
#>
[CmdletBinding()]
param(
    [switch]$BorrarArchivos,
    [switch]$Forzar
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

if (-not $Forzar) {
    $resp = Read-Host "Se borrara la base de datos 'ocr' completa. Escribe SI para continuar"
    if ($resp -ne "SI") { Write-Host "Cancelado."; exit 0 }
}

Write-Host "==> Bajando contenedores" -ForegroundColor Cyan
docker compose down --remove-orphans
if (-not $?) { exit 1 }

Write-Host "==> Borrando volumen ocr-mssql-data" -ForegroundColor Cyan
docker volume rm ocr-mssql-data 2>$null
if (-not $?) { Write-Host "(el volumen no existia o ya estaba borrado)" -ForegroundColor Yellow }

if ($BorrarArchivos) {
    Write-Host "==> Borrando volumen ocr-archivos-data" -ForegroundColor Cyan
    docker volume rm ocr-archivos-data 2>$null
    if (-not $?) { Write-Host "(el volumen no existia o ya estaba borrado)" -ForegroundColor Yellow }
}

Write-Host "==> Levantando de nuevo" -ForegroundColor Cyan
& "$PSScriptRoot\levantar.ps1" -SinBuild
