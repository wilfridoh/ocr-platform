<#
.SYNOPSIS
  Levanta la plataforma OCR completa con Docker Compose.

.DESCRIPTION
  1. Verifica que Docker este corriendo.
  2. Copia .env.example a .env si no existe.
  3. Avisa si el puerto de SQL Server configurado ya esta ocupado.
  4. docker compose up -d --build
  5. Espera a que GET /api/salud responda 200.
  6. Imprime las URLs utiles.

.PARAMETER SinBuild
  No reconstruye las imagenes (usa las ya existentes).

.PARAMETER Servicios
  Lista de servicios a levantar (por defecto todos).

.EXAMPLE
  .\scripts\levantar.ps1
  .\scripts\levantar.ps1 -SinBuild
  .\scripts\levantar.ps1 -Servicios mssql,db-init
#>
[CmdletBinding()]
param(
    [switch]$SinBuild,
    [string[]]$Servicios = @(),
    [int]$TimeoutSegundos = 240
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

function Escribir-Paso($texto) { Write-Host "`n==> $texto" -ForegroundColor Cyan }

# 1. Docker disponible
Escribir-Paso "Comprobando Docker"
docker info *> $null
if (-not $?) {
    Write-Host "Docker no responde. Abre Docker Desktop y vuelve a intentar." -ForegroundColor Red
    exit 1
}

# 2. .env
Escribir-Paso "Archivo .env"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Se creo .env a partir de .env.example (valores de desarrollo)." -ForegroundColor Yellow
} else {
    Write-Host ".env ya existe, se conserva."
}

# Leer variables del .env (solo las que necesitamos para mensajes)
$env_vars = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { $env_vars[$matches[1]] = $matches[2].Trim() }
}
function Valor($nombre, $defecto) { if ($env_vars.ContainsKey($nombre) -and $env_vars[$nombre] -ne "") { $env_vars[$nombre] } else { $defecto } }

$puertoSql   = [int](Valor "MSSQL_PUERTO_HOST" 1433)
$puertoApi   = [int](Valor "BACKEND_PUERTO_HOST" 8000)
$puertoMcp   = [int](Valor "MCP_PUERTO_HOST" 8001)
$puertoFront = [int](Valor "FRONTEND_PUERTO_HOST" 3000)

# 3. Puertos ocupados (solo aviso; si es nuestro propio contenedor no pasa nada)
Escribir-Paso "Comprobando puertos del host"
foreach ($p in @($puertoSql, $puertoApi, $puertoMcp, $puertoFront)) {
    $ocupado = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($ocupado) {
        $pid_ = ($ocupado | Select-Object -First 1).OwningProcess
        $proc = (Get-Process -Id $pid_ -ErrorAction SilentlyContinue).ProcessName
        Write-Host "Aviso: el puerto $p ya esta en uso (proceso: $proc, PID $pid_). Si no es un contenedor de este proyecto, cambia el puerto en .env." -ForegroundColor Yellow
    } else {
        Write-Host "Puerto $p libre."
    }
}

# 4. Levantar
Escribir-Paso "docker compose up"
$args_ = @("compose", "up", "-d")
if (-not $SinBuild) { $args_ += "--build" }
$args_ += $Servicios
& docker @args_
if (-not $?) {
    Write-Host "docker compose up fallo. Revisa la salida anterior o ejecuta .\scripts\logs.ps1" -ForegroundColor Red
    exit 1
}

# 5. Esperar salud del backend (solo si se levanta el backend)
$levantaBackend = ($Servicios.Count -eq 0) -or ($Servicios -contains "backend")
if ($levantaBackend) {
    Escribir-Paso "Esperando a que la API responda en http://localhost:$puertoApi/api/salud"
    $inicio = Get-Date
    $ok = $false
    while (((Get-Date) - $inicio).TotalSeconds -lt $TimeoutSegundos) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:$puertoApi/api/salud" -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) { $ok = $true; break }
        } catch { }
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 3
    }
    Write-Host ""
    if ($ok) {
        Write-Host "API saludable." -ForegroundColor Green
        try { Write-Host $r.Content } catch { }
    } else {
        Write-Host "La API no respondio en $TimeoutSegundos s. Estado de los contenedores:" -ForegroundColor Yellow
        docker compose ps
        Write-Host "Usa .\scripts\logs.ps1 backend  (o db-init / mssql) para ver el detalle." -ForegroundColor Yellow
    }
}

# 6. URLs
Escribir-Paso "URLs"
Write-Host ("  Frontend      : http://localhost:{0}" -f $puertoFront)
Write-Host ("  API           : http://localhost:{0}/api" -f $puertoApi)
Write-Host ("  Swagger       : http://localhost:{0}/docs" -f $puertoApi)
Write-Host ("  Salud         : http://localhost:{0}/api/salud" -f $puertoApi)
Write-Host ("  MCP (http)    : http://localhost:{0}/mcp" -f $puertoMcp)
Write-Host ("  SQL Server    : localhost,{0}   usuario sa   BD {1}" -f $puertoSql, (Valor "DB_NOMBRE" "ocr"))
Write-Host ("  API key (dev) : {0}" -f (Valor "API_KEY" "(ver .env)"))
Write-Host ""
docker compose ps
