<#
.SYNOPSIS
  Muestra los logs de la plataforma OCR (todos o de un servicio).

.PARAMETER Servicio
  mssql | db-init | backend | mcp | frontend. Vacio = todos.

.PARAMETER Lineas
  Cuantas lineas previas mostrar (por defecto 200).

.PARAMETER SinSeguir
  No queda escuchando (solo imprime y sale).

.EXAMPLE
  .\scripts\logs.ps1
  .\scripts\logs.ps1 backend
  .\scripts\logs.ps1 db-init -SinSeguir
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("", "mssql", "db-init", "backend", "mcp", "frontend")]
    [string]$Servicio = "",
    [int]$Lineas = 200,
    [switch]$SinSeguir
)

$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

$args_ = @("compose", "logs", "--tail", "$Lineas", "--timestamps")
if (-not $SinSeguir) { $args_ += "-f" }
if ($Servicio -ne "") { $args_ += $Servicio }

& docker @args_
