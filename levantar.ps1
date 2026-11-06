# Levanta MassSend en Windows sin configurar nada e informa el estado de cada servicio.
# Equivalente de levantar.sh, con las mismas opciones.
#
# Uso: .\levantar.cmd [opciones]   (o .\levantar.ps1 [opciones] desde PowerShell)
#   (sin opciones)      levanta el sistema completo en produccion: API, workers, WhatsApp,
#                       Ollama, PocketBase, Postgres, Redis y Mailpit. Los datos se conservan
#   -s, --sin NOMBRE    no usa una integracion aunque exista (ej. --sin paypal); se repite
#   -a, --actualizar    trae lo ultimo de origin/main (git pull --ff-only) antes de levantar
#       --qr            muestra el codigo QR para vincular WhatsApp (sal con Ctrl+C)
#       --estado        informa el estado sin levantar nada
#       --apagar        detiene todo; en produccion los datos se conservan
#       --borrar-datos  detiene produccion y borra sus datos (pide confirmacion)
#   -h, --ayuda         muestra esta ayuda
#
# Modo prueba (adaptadores simulados y base en memoria, para Postman):
#   -p, --prueba        usa el modo prueba en lugar de produccion
#   -l, --limpio        (prueba) borra la base de prueba antes de levantar
#   -i, --ia            (prueba) agrega Ollama aunque no exista backend\.env.ia
#   Ejemplos: .\levantar.cmd --prueba    .\levantar.cmd --prueba --apagar
#
# Integraciones: si existe backend\.env.<nombre> (gmail, google, paypal, payphone, ia)
# con sus valores, se usa sola. Sin ella, en produccion esa funcion queda "no configurada"
# (los correos van a Mailpit) y en prueba se simula.
# Los secretos internos de produccion se generan la primera vez en backend\.env.secretos:
# no lo borres mientras existan los datos. backend\.env es opcional (ajustes extra).
# Variables: API_PORT (8000), MAILPIT_PORT (8025), FRONTEND_PORT (5173), PROYECTO (masssend-ci).
# Ejemplo: $env:API_PORT = "8080"; .\levantar.cmd
# Requiere Docker Desktop (WSL 2) en ejecucion. Nunca imprime los valores de los .env.

$ErrorActionPreference = 'Continue'
$Raiz = $PSScriptRoot
Set-Location -LiteralPath $Raiz

$Proyecto = if ($env:PROYECTO) { $env:PROYECTO } else { 'masssend-ci' }
$ProyectoProd = 'masssend'
if (-not $env:API_PORT) { $env:API_PORT = '8000' }
if (-not $env:MAILPIT_PORT) { $env:MAILPIT_PORT = '8025' }
if (-not $env:FRONTEND_PORT) { $env:FRONTEND_PORT = '5173' }
$BaseEnv = 'backend/tests/ci.env'
$Secretos = 'backend/.env.secretos'
$EnvExtra = 'backend/.env'
$CredsWhatsapp = 'backend/whatsapp_api/auth_info_baileys/creds.json'
$script:Modelo = if ($env:OLLAMA_MODEL_CI) { $env:OLLAMA_MODEL_CI } else { 'qwen2.5:0.5b' }
$Utf8SinBom = New-Object System.Text.UTF8Encoding $false

function Ruta([string]$relativa) { Join-Path $Raiz $relativa }
function Info([string]$texto) { Write-Host $texto }
function Aviso([string]$texto) { Write-Host "! $texto" -ForegroundColor Yellow }
function Falla([string]$texto) { Write-Host "X $texto" -ForegroundColor Red; exit 1 }
function Titulo([string]$texto) { Write-Host $texto -ForegroundColor White }
function Fila([string]$nombre, [string]$color, [string]$estado, [string]$detalle) {
  Write-Host ('  {0,-11} ' -f $nombre) -NoNewline
  if ($color) { Write-Host ('{0,-15} ' -f $estado) -ForegroundColor $color -NoNewline }
  else { Write-Host ('{0,-15} ' -f $estado) -NoNewline }
  Write-Host $detalle
}

function Ayuda {
  foreach ($l in [System.IO.File]::ReadAllLines((Ruta 'levantar.ps1'))) {
    if ($l.Trim() -eq '') { break }
    Write-Host ($l -replace '^# ?', '')
  }
}

# --- Opciones ---
$Modo = 'produccion'; $Accion = 'levantar'
$Limpio = $false; $script:IA = $false; $Actualizar = $false
$Excluidas = @(); $SoloPrueba = @()
$Argumentos = @($args)
$i = 0
while ($i -lt $Argumentos.Count) {
  $op = [string]$Argumentos[$i]
  switch -CaseSensitive ($op) {
    { $_ -in '-p', '--prueba' } { $Modo = 'prueba'; break }
    { $_ -in '-l', '--limpio' } { $Limpio = $true; $SoloPrueba += $op; break }
    { $_ -in '-i', '--ia' } { $script:IA = $true; $SoloPrueba += $op; break }
    { $_ -in '-s', '--sin' } {
      if ($i + 1 -ge $Argumentos.Count) { Falla '--sin necesita un nombre, por ejemplo: --sin paypal' }
      $i++; $Excluidas += [string]$Argumentos[$i]; break
    }
    { $_ -in '-a', '--actualizar' } { $Actualizar = $true; break }
    '--qr' { $Accion = 'qr'; break }
    '--estado' { $Accion = 'estado'; break }
    '--apagar' { $Accion = 'apagar'; break }
    '--borrar-datos' { $Accion = 'borrar'; break }
    { $_ -in '-h', '--ayuda' } { Ayuda; exit 0 }
    default { Falla "Opcion desconocida: $op (usa --ayuda)" }
  }
  $i++
}

if ($Modo -eq 'produccion' -and $SoloPrueba.Count -gt 0) {
  Falla "$($SoloPrueba[0]) solo existe en modo prueba. Agrega --prueba (en produccion usa --borrar-datos para empezar de cero)."
}
if ($Modo -eq 'prueba' -and $Accion -in 'qr', 'borrar') { Falla 'Esa opcion es solo de produccion; quita --prueba.' }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Falla 'Docker no esta instalado (instala Docker Desktop).' }
& docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Falla 'Falta Docker Compose v2 o Docker Desktop no esta en ejecucion.' }

# Lee el valor de una variable sin ejecutar el archivo.
function Valor([string]$clave, [string]$archivo) {
  $ruta = Ruta $archivo
  if (-not (Test-Path -LiteralPath $ruta)) { return '' }
  $v = ''
  $patron = '^\s*' + [regex]::Escape($clave) + '=(.*)$'
  foreach ($l in [System.IO.File]::ReadAllLines($ruta)) {
    if ($l -match $patron) { $v = $Matches[1] }
  }
  $v = $v.TrimEnd("`r")
  if ($v.StartsWith('"')) { $v = $v.Substring(1) }
  if ($v.EndsWith('"')) { $v = $v.Substring(0, $v.Length - 1) }
  if ($v.StartsWith("'")) { $v = $v.Substring(1) }
  if ($v.EndsWith("'")) { $v = $v.Substring(0, $v.Length - 1) }
  return $v
}

# Devuelve las variables obligatorias que faltan en el archivo real.
function Faltantes([string]$plantilla, [string]$real) {
  $opcional = $false; $faltan = @()
  foreach ($l in [System.IO.File]::ReadAllLines((Ruta $plantilla))) {
    $l = $l.TrimEnd("`r")
    if ($l.StartsWith('#')) { if ($l -like '*Opcional*') { $opcional = $true }; continue }
    if ($l -eq '') { $opcional = $false; continue }
    $clave = $l.Split('=')[0]
    if ($clave -cmatch '^[A-Z0-9_]+$' -and -not $opcional -and (Valor $clave $real) -eq '') { $faltan += $clave }
    $opcional = $false
  }
  return ($faltan -join ' ')
}

# Revisa cada integracion. Estados: real, omitida, sin-archivo, incompleta.
$script:Archivos = @(); $script:Activas = @(); $script:Integraciones = @()
$script:Postman = @(); $script:PerfilesExtra = @()
function Detectar {
  $plantillas = Get-ChildItem -Force -LiteralPath (Ruta 'backend') -Filter '.env.*.example' | Sort-Object Name
  foreach ($p in $plantillas) {
    $nombre = $p.Name.Substring(5); $nombre = $nombre.Substring(0, $nombre.Length - 8)
    $plantilla = "backend/$($p.Name)"; $real = "backend/.env.$nombre"
    if ($Excluidas -contains $nombre) {
      $estado = 'omitida'; $detalle = "pediste --sin $nombre"
    } elseif (-not (Test-Path -LiteralPath (Ruta $real))) {
      $estado = 'sin-archivo'; $detalle = "crea $real desde $plantilla"
    } else {
      $faltan = Faltantes $plantilla $real
      if ($faltan) { $estado = 'incompleta'; $detalle = "faltan valores en ${real}: $faltan" }
      else {
        $estado = 'real'; $detalle = $real
        $script:Archivos += @('--env-file', $real); $script:Activas += $nombre
        foreach ($l in [System.IO.File]::ReadAllLines((Ruta $plantilla))) {
          if ($l -like '# Postman:*') { $script:Postman += ($l -replace '^# Postman:\s*', '').TrimEnd("`r") }
          if ($l -like '# Perfil:*') { $script:PerfilesExtra += ($l -replace '^# Perfil:\s*', '').TrimEnd("`r") }
        }
        if ($nombre -eq 'ia' -and (Valor 'OLLAMA_MODEL_CI' $real)) { $script:Modelo = Valor 'OLLAMA_MODEL_CI' $real }
      }
    }
    $script:Integraciones += , @($nombre, $estado, $detalle)
  }
}

function Estado-De([string]$nombre) {
  foreach ($fila in $script:Integraciones) { if ($fila[0] -eq $nombre) { return $fila } }
  return @($nombre, 'sin-archivo', '')
}

function Actualizar-Repo {
  if (-not $Actualizar) { return }
  Titulo 'Trayendo lo ultimo de origin/main...'
  & git pull --ff-only origin main
  if ($LASTEXITCODE -ne 0) { Falla "No se pudo actualizar sin mezclar. Revisa 'git status'." }
}

# ============================== MODO PRODUCCION ==============================

function Aleatorio([int]$bytes) {
  $buffer = New-Object byte[] $bytes
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($buffer); $rng.Dispose()
  return -join ($buffer | ForEach-Object { $_.ToString('x2') })
}

function Hay-DatosProd {
  & docker volume inspect "${ProyectoProd}_masssend_postgres_data" *> $null
  return ($LASTEXITCODE -eq 0)
}

# Genera una sola vez los secretos internos; si faltan claves nuevas, solo agrega esas.
function Asegurar-Secretos {
  $ruta = Ruta $Secretos
  if (-not (Test-Path -LiteralPath $ruta)) {
    if (Hay-DatosProd) { Falla "Hay datos de produccion pero falta $Secretos, que tiene la clave de la base. Recuperalo o borra los datos con --borrar-datos." }
    [System.IO.File]::WriteAllText($ruta, "# Generado por levantar.ps1. No lo borres ni lo compartas: la base usa esta clave.`n", $Utf8SinBom)
    Info "Genere los secretos internos en $Secretos."
  }
  $claves = 'SECRET_KEY', 'JWT_SECRET_KEY', 'POSTGRES_PASSWORD', 'WHATSAPP_WEBHOOK_TOKEN',
            'PB_SUPERUSER_EMAIL', 'PB_SUPERUSER_PASSWORD', 'ADMIN_EMAIL', 'ADMIN_PASSWORD'
  foreach ($clave in $claves) {
    if (Valor $clave $Secretos) { continue }
    switch ($clave) {
      'POSTGRES_PASSWORD' {
        if (Hay-DatosProd) { Falla "Falta POSTGRES_PASSWORD en $Secretos y la base ya existe. Recupera la clave o usa --borrar-datos." }
        $nuevo = Aleatorio 32
      }
      { $_ -in 'PB_SUPERUSER_EMAIL', 'ADMIN_EMAIL' } { $nuevo = 'admin@masssend.local' }
      { $_ -in 'PB_SUPERUSER_PASSWORD', 'ADMIN_PASSWORD' } { $nuevo = Aleatorio 16 }
      default { $nuevo = Aleatorio 32 }
    }
    [System.IO.File]::AppendAllText($ruta, "$clave=$nuevo`n", $Utf8SinBom)
  }
}

function Archivos-Prod {
  $lista = @()
  if (Test-Path -LiteralPath (Ruta $Secretos)) { $lista += @('--env-file', $Secretos) }
  if (Test-Path -LiteralPath (Ruta $EnvExtra)) { $lista += @('--env-file', $EnvExtra) }
  return ($lista + $script:Archivos)
}

function Compose-Prod { $a = $script:ArchivosProd; & docker compose -p $ProyectoProd @a --profile real @args }

# Cualquier respuesta HTTP < 500 indica que gunicorn y Django arrancaron.
function Api-Responde {
  $codigo = "import http.client as h; c=h.HTTPConnection('localhost',8000,timeout=3); c.request('GET','/api/v1/salud'); exit(0 if c.getresponse().status<500 else 1)"
  Compose-Prod exec -T backend python -c $codigo *> $null
  return ($LASTEXITCODE -eq 0)
}

# El frontend responde y su proxy llega a la API.
function Web-Responde {
  Compose-Prod exec -T frontend wget -qO /dev/null http://127.0.0.1/api/v1/salud *> $null
  return ($LASTEXITCODE -eq 0)
}

function Esperar-Backend {
  for ($n = 1; $n -le 90; $n++) {
    if (Api-Responde) { return $true }
    Start-Sleep -Seconds 2
  }
  return $false
}

function Tiene-Modelo {
  $lista = Compose-Prod exec -T ollama ollama list 2> $null
  return [bool]($lista -match ('^' + [regex]::Escape($script:Modelo)))
}

function Informe-Prod {
  Info ''
  Titulo 'Estado de MassSend (produccion)'
  if (Api-Responde) { Fila 'API' 'Green' 'lista' "http://localhost:$($env:API_PORT)/api/v1/salud" }
  else { Fila 'API' 'Red' 'no responde' "revisa: docker compose -p $ProyectoProd logs backend" }
  if (Web-Responde) { Fila 'Web' 'Green' 'lista' "http://localhost:$($env:FRONTEND_PORT)" }
  else { Fila 'Web' 'Red' 'no responde' "revisa: docker compose -p $ProyectoProd logs frontend" }

  $gmail = Estado-De 'gmail'
  if ($gmail[1] -eq 'real') { Fila 'Correos' 'Green' 'Gmail' 'llegan a los destinatarios reales' }
  else { Fila 'Correos' 'Yellow' 'Mailpit' "http://localhost:$($env:MAILPIT_PORT) (no salen a internet; $($gmail[2]))" }

  foreach ($fila in $script:Integraciones) {
    $nombre = $fila[0]
    if ($nombre -in 'gmail', 'ia') { continue }
    $etiqueta = switch ($nombre) { 'google' { 'Google' } 'paypal' { 'PayPal' } 'payphone' { 'PayPhone' } default { $nombre } }
    if ($fila[1] -eq 'real') {
      $detalle = ''
      if ($nombre -eq 'paypal') {
        $url = Valor 'PAYPAL_BASE_URL' 'backend/.env.paypal'
        if ($url -eq '' -or $url -like '*sandbox*') { $detalle = 'Sandbox (dinero ficticio)' }
      }
      if ($nombre -eq 'payphone') { $detalle = "paga desde http://localhost:$($env:FRONTEND_PORT)/creditos" }
      Fila $etiqueta 'Green' 'activo' $detalle
    } else {
      Fila $etiqueta 'Yellow' 'no configurado' $fila[2]
    }
  }

  if (Tiene-Modelo) { Fila 'Asistente' 'Green' 'Ollama' "modelo $($script:Modelo)" }
  else { Fila 'Asistente' 'Yellow' 'sin modelo' "se descarga al levantar ($($script:Modelo))" }

  if (Test-Path -LiteralPath (Ruta $CredsWhatsapp)) { Fila 'WhatsApp' 'Green' 'vinculado' 'sesion guardada' }
  else { Fila 'WhatsApp' 'Yellow' 'sin vincular' 'escanea el QR con: .\levantar.cmd --qr' }

  Fila 'Archivos' 'Green' 'PocketBase' 'interno'
  Fila 'Admin' '' 'creado' "$(Valor 'ADMIN_EMAIL' $Secretos) (clave: ADMIN_PASSWORD en $Secretos)"

  $total = 0; $corriendo = 0; $caidos = @()
  foreach ($linea in @(Compose-Prod ps -a --format '{{.Service}}|{{.State}}' 2> $null)) {
    if (-not $linea) { continue }
    $partes = ([string]$linea).Split('|')
    $total++
    if ($partes[1] -eq 'running') { $corriendo++ } else { $caidos += "$($partes[0])($($partes[1]))" }
  }
  if ($total -eq 0) { Fila 'Servicios' 'Yellow' 'apagados' 'levanta con: .\levantar.cmd' }
  elseif ($caidos.Count -eq 0) { Fila 'Servicios' 'Green' "$corriendo/$total activos" '' }
  else { Fila 'Servicios' 'Red' "$corriendo/$total activos" "con problemas: $($caidos -join ' ')" }

  if ($script:Activas.Count -lt $script:Integraciones.Count) {
    Info ''
    Info 'Para activar lo que falta, crea el archivo indicado y vuelve a ejecutar .\levantar.cmd.'
  }
}

function Produccion {
  Detectar
  $script:ArchivosProd = Archivos-Prod
  $existenSecretos = Test-Path -LiteralPath (Ruta $Secretos)

  if ($Accion -in 'apagar', 'estado', 'qr' -and -not $existenSecretos) {
    Info 'Produccion nunca se ha levantado en este equipo. Ejecuta: .\levantar.cmd'; return
  }
  switch ($Accion) {
    'apagar' {
      Compose-Prod down --remove-orphans
      Info 'Contenedores detenidos. Los datos se conservan; vuelve a levantar con .\levantar.cmd'; return
    }
    'estado' { Informe-Prod; return }
    'qr' {
      if (Test-Path -LiteralPath (Ruta $CredsWhatsapp)) { Info 'WhatsApp ya esta vinculado; el registro muestra su estado.' }
      Info 'Escanea el QR desde WhatsApp > Dispositivos vinculados. Sal con Ctrl+C.'
      Compose-Prod logs -f --tail 60 whatsapp; return
    }
    'borrar' {
      Aviso 'Esto borra la base de datos, los archivos de PocketBase y los modelos de Ollama.'
      $respuesta = Read-Host 'Escribe BORRAR para confirmar'
      if ($respuesta -cne 'BORRAR') { Falla 'Cancelado; no se borro nada.' }
      if ($existenSecretos) { Compose-Prod down -v --remove-orphans }
      else { & docker volume rm "${ProyectoProd}_masssend_postgres_data" *> $null }
      Info 'Datos de produccion borrados.'; return
    }
  }

  Asegurar-Secretos
  $script:ArchivosProd = Archivos-Prod

  $ciArriba = & docker ps -q --filter "label=com.docker.compose.project=$Proyecto" 2> $null
  if ($ciArriba) {
    Info 'Apagando el modo prueba, que usa los mismos puertos...'
    & docker compose -p $Proyecto --env-file $BaseEnv --profile ci --profile ia down -v --remove-orphans *> $null
  }

  Actualizar-Repo

  Titulo 'Construyendo y levantando MassSend (la primera vez tarda varios minutos)...'
  Compose-Prod up --build -d --remove-orphans
  if ($LASTEXITCODE -ne 0) { Falla 'Docker Compose no pudo levantar los servicios.' }

  Info 'Esperando a que la API responda...'
  if (-not (Esperar-Backend)) {
    Aviso 'La API no respondio. Ultimas lineas del registro:'
    Compose-Prod logs --tail 40 backend
    Informe-Prod
    exit 1
  }

  # Crea el administrador la primera vez; si ya existe, no cambia nada.
  Compose-Prod exec -T backend python manage.py createsuperuser --noinput *> $null

  if (-not (Tiene-Modelo)) {
    Info "Descargando el modelo de IA $($script:Modelo) (solo la primera vez)..."
    Compose-Prod exec -T ollama ollama pull $script:Modelo *> $null
    if ($LASTEXITCODE -ne 0) { Aviso "No se pudo descargar $($script:Modelo)." }
  }

  Informe-Prod
  Info ''
  Info 'Apagar (conserva datos): .\levantar.cmd --apagar   Ver estado: .\levantar.cmd --estado'
}

# ================================ MODO PRUEBA ================================

function Mostrar-Integraciones {
  Titulo 'Integraciones'
  foreach ($fila in $script:Integraciones) {
    switch ($fila[1]) {
      'real' { $estado = 'real'; $color = 'Green' }
      'omitida' { $estado = 'omitida'; $color = 'Yellow' }
      'incompleta' { $estado = 'simulada'; $color = 'Yellow' }
      default { $estado = 'simulada'; $color = 'Gray' }
    }
    Write-Host ('  {0,-8} ' -f $fila[0]) -NoNewline
    Write-Host ('{0,-10} ' -f $estado) -ForegroundColor $color -NoNewline
    Write-Host $fila[2]
  }
  if ($script:Integraciones.Count -eq 0) { Info '  (no hay plantillas backend/.env.*.example)' }
}

function Compose-Prueba { $a = $script:ArchivosPrueba; & docker compose -p $Proyecto @a @args }

function Prueba {
  if (-not (Test-Path -LiteralPath (Ruta $BaseEnv))) { Falla "No encuentro $BaseEnv. Ejecuta el script desde el repositorio." }
  Detectar
  $script:ArchivosPrueba = @('--env-file', $BaseEnv) + $script:Archivos
  $perfiles = @('--profile', 'ci')
  foreach ($perfil in $script:PerfilesExtra) {
    if ($perfil -eq 'ia') { $script:IA = $true } else { $perfiles += @('--profile', $perfil) }
  }
  if ($script:IA) { $perfiles += @('--profile', 'ia') }

  switch ($Accion) {
    'apagar' {
      Compose-Prueba --profile ci --profile ia down -v --remove-orphans
      Info 'Contenedores detenidos y datos de prueba borrados.'; return
    }
    'estado' { Mostrar-Integraciones; Info ''; Compose-Prueba --profile ci --profile ia ps; return }
  }

  $prodArriba = & docker ps -q --filter "label=com.docker.compose.project=$ProyectoProd" 2> $null
  if ($prodArriba) { Falla 'Produccion esta arriba y usa los mismos puertos. Apagala con: .\levantar.cmd --apagar' }

  Actualizar-Repo

  Mostrar-Integraciones
  Info ''

  if ($script:IA) { $env:GENERADOR_TEXTO_CI = 'ollama' }

  if ($Limpio) {
    Info 'Borrando la base de prueba anterior...'
    Compose-Prueba --profile ci --profile ia down -v --remove-orphans *> $null
  }

  Titulo 'Construyendo y levantando (puede tardar la primera vez)...'
  Compose-Prueba @perfiles up --build -d --wait --remove-orphans
  if ($LASTEXITCODE -ne 0) {
    Aviso 'El backend no arranco. Ultimas lineas del registro:'
    Compose-Prueba @perfiles logs --tail 40 backend-ci
    exit 1
  }

  if ($script:IA) {
    $lista = Compose-Prueba @perfiles exec -T ollama-ci ollama list 2> $null
    if (-not ($lista -match ('^' + [regex]::Escape($script:Modelo)))) {
      Info "Descargando el modelo $($script:Modelo) (solo la primera vez)..."
      Compose-Prueba @perfiles exec -T ollama-ci ollama pull $script:Modelo
    }
  }

  Info ''
  Write-Host 'MassSend (modo prueba) esta listo.' -ForegroundColor Green
  Info "  API:        http://localhost:$($env:API_PORT)/api/v1/salud"
  if ($script:Activas -contains 'gmail') { Info '  Correos:    llegan a tu Gmail' }
  else { Info "  Correos:    http://localhost:$($env:MAILPIT_PORT) (Mailpit)" }
  Info "  Web:        http://localhost:$($env:FRONTEND_PORT) (tambien abre ahi el url_pago de PayPhone)"
  if ($script:IA) { Info "  Asistente:  Ollama ($($script:Modelo))" }
  else { Info '  Asistente:  simulado (crea backend\.env.ia para Ollama)' }
  Info '  Staff:      staff@prueba.local / clave-larga-123'
  Info ''
  Titulo 'En Postman (entorno MassSend local)'
  if ($env:API_PORT -ne '8000') { Info "  - baseUrl=http://localhost:$($env:API_PORT)" }
  if ($env:MAILPIT_PORT -ne '8025') { Info "  - mailpitUrl=http://localhost:$($env:MAILPIT_PORT)" }
  foreach ($indicacion in $script:Postman) { Info "  - $indicacion" }
  if ($script:Postman.Count -eq 0) { Info '  - deja los valores por defecto (todo simulado)' }
  Info '  - guarda el entorno con Ctrl+S antes de ejecutar'
  Info ''
  Info 'Apagar: .\levantar.cmd --prueba --apagar   Empezar de cero: .\levantar.cmd --prueba --limpio'
}

if ($Modo -eq 'produccion') { Produccion } else { Prueba }
exit 0
