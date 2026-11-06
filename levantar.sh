#!/usr/bin/env bash
# Levanta MassSend sin configurar nada y al final informa el estado de cada servicio.
#
# Uso: ./levantar.sh [opciones]
#   (sin opciones)      levanta el sistema completo en produccion: API, workers, WhatsApp,
#                       Ollama, PocketBase, Postgres, Redis, Mailpit y la web. Los datos se conservan
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
#   -i, --ia            (prueba) agrega Ollama aunque no exista backend/.env.ia
#   Ejemplos: ./levantar.sh --prueba    ./levantar.sh --prueba --apagar
#
# Integraciones: cada backend/.env.<nombre>.example es una integracion (gmail, google,
# paypal, payphone, ia). Si existe backend/.env.<nombre> con sus valores, se usa sola en
# los dos modos. Sin ella, en produccion esa funcion queda "no configurada" (los correos
# van a Mailpit) y en prueba se simula. En la plantilla:
#   "# Postman: ..."      indica que variables cambiar en el entorno de Postman
#   "# Opcional. ..."     encima de una variable permite dejarla vacia
#   "# Perfil: ..."       agrega un perfil de compose en modo prueba (ej. ia levanta Ollama)
#
# Los secretos internos de produccion (base, firma, PocketBase, admin) se generan la
# primera vez en backend/.env.secretos: no lo borres mientras existan los datos.
# backend/.env es opcional y solo sirve para ajustes extra (ALLOWED_HOSTS, FRONTEND_URL).
# Variables: API_PORT (8000), MAILPIT_PORT (8025), FRONTEND_PORT (5173), PROYECTO (masssend-ci).
# Nunca imprime los valores de los archivos .env.
# Equivalente en Windows: levantar.cmd (o levantar.ps1) con las mismas opciones.

set -euo pipefail
cd "$(dirname "$0")"

PROYECTO="${PROYECTO:-masssend-ci}"
PROYECTO_PROD="masssend"
export API_PORT="${API_PORT:-8000}"
export MAILPIT_PORT="${MAILPIT_PORT:-8025}"
export FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BASE_ENV="backend/tests/ci.env"
SECRETOS="backend/.env.secretos"
ENV_EXTRA="backend/.env"
CREDS_WHATSAPP="backend/whatsapp_api/auth_info_baileys/creds.json"

# Baileys crea creds.json al arrancar; solo al vincular con exito guarda "account"
# (la identidad firmada del dispositivo). "me" aparece apenas se pide un codigo.
whatsapp_vinculado() {
  [ -f "$CREDS_WHATSAPP" ] && grep -q '"account":' "$CREDS_WHATSAPP" 2>/dev/null
}
MODELO="${OLLAMA_MODEL_CI:-qwen2.5:0.5b}"

if [ -t 1 ]; then
  VERDE=$'\e[32m'; AMARILLO=$'\e[33m'; ROJO=$'\e[31m'; NEGRITA=$'\e[1m'; NORMAL=$'\e[0m'
else
  VERDE=""; AMARILLO=""; ROJO=""; NEGRITA=""; NORMAL=""
fi
info() { printf '%s\n' "$*"; }
aviso() { printf '%s! %s%s\n' "$AMARILLO" "$*" "$NORMAL"; }
falla() { printf '%sX %s%s\n' "$ROJO" "$*" "$NORMAL" >&2; exit 1; }
fila() { printf '  %-11s %s%-15s%s %s\n' "$1" "$2" "$3" "$NORMAL" "${4:-}"; }

ayuda() { sed -n '2,/^$/p' "$0" | sed -E 's/^# ?//'; }

MODO="produccion"; ACCION="levantar"; LIMPIO=0; IA=0; ACTUALIZAR=0; EXCLUIDAS=(); SOLO_PRUEBA=()
while [ $# -gt 0 ]; do
  case "$1" in
    -p|--prueba) MODO="prueba" ;;
    -l|--limpio) LIMPIO=1; SOLO_PRUEBA+=("$1") ;;
    -i|--ia) IA=1; SOLO_PRUEBA+=("$1") ;;
    -s|--sin) [ $# -ge 2 ] || falla "--sin necesita un nombre, por ejemplo: --sin paypal"
              EXCLUIDAS+=("$2"); shift ;;
    -a|--actualizar) ACTUALIZAR=1 ;;
    --qr) ACCION="qr" ;;
    --estado) ACCION="estado" ;;
    --apagar) ACCION="apagar" ;;
    --borrar-datos) ACCION="borrar" ;;
    -h|--ayuda) ayuda; exit 0 ;;
    *) falla "Opcion desconocida: $1 (usa --ayuda)" ;;
  esac
  shift
done

if [ "$MODO" = "produccion" ] && [ "${#SOLO_PRUEBA[@]}" -gt 0 ]; then
  falla "${SOLO_PRUEBA[0]} solo existe en modo prueba. Agrega --prueba (en produccion usa --borrar-datos para empezar de cero)."
fi
if [ "$MODO" = "prueba" ]; then
  case "$ACCION" in qr|borrar) falla "Esa opcion es solo de produccion; quita --prueba." ;; esac
fi

command -v docker >/dev/null || falla "Docker no esta instalado."
docker compose version >/dev/null 2>&1 || falla "Falta Docker Compose v2 o Docker no esta en ejecucion."

# Lee el valor de una variable sin ejecutar el archivo (no hace source).
valor() {
  local linea
  [ -f "$2" ] || return 0
  linea=$(grep -E "^[[:space:]]*$1=" "$2" | tail -n 1 || true)
  linea="${linea#*=}"
  linea="${linea%$'\r'}"
  linea="${linea#\"}"; linea="${linea%\"}"
  linea="${linea#\'}"; linea="${linea%\'}"
  printf '%s' "$linea"
}

# Imprime las variables obligatorias que faltan en el archivo real.
faltantes() {
  local plantilla="$1" real="$2" opcional=0 linea clave
  while IFS= read -r linea || [ -n "$linea" ]; do
    linea="${linea%$'\r'}"
    case "$linea" in
      \#*) case "$linea" in *Opcional*) opcional=1 ;; esac; continue ;;
      "") opcional=0; continue ;;
    esac
    clave="${linea%%=*}"
    if [[ "$clave" =~ ^[A-Z0-9_]+$ ]] && [ "$opcional" -eq 0 ] && [ -z "$(valor "$clave" "$real")" ]; then
      printf '%s ' "$clave"
    fi
    opcional=0
  done < "$plantilla"
}

excluida() {
  local nombre
  for nombre in "${EXCLUIDAS[@]+"${EXCLUIDAS[@]}"}"; do [ "$nombre" = "$1" ] && return 0; done
  return 1
}

activa() { [[ " ${ACTIVAS[*]-} " == *" $1 "* ]]; }

# Revisa cada integracion. Estados: real, omitida, sin-archivo, incompleta.
ARCHIVOS=(); ACTIVAS=(); NOMBRES=(); ESTADOS=(); DETALLES=(); POSTMAN=(); PERFILES_EXTRA=()
detectar() {
  local plantilla nombre real faltan linea
  for plantilla in backend/.env.*.example; do
    [ -e "$plantilla" ] || continue
    nombre="${plantilla#backend/.env.}"; nombre="${nombre%.example}"
    real="backend/.env.$nombre"
    NOMBRES+=("$nombre")
    if excluida "$nombre"; then
      ESTADOS+=("omitida"); DETALLES+=("pediste --sin $nombre")
    elif [ ! -f "$real" ]; then
      ESTADOS+=("sin-archivo"); DETALLES+=("crea $real desde $plantilla")
    else
      faltan=$(faltantes "$plantilla" "$real")
      if [ -n "$faltan" ]; then
        ESTADOS+=("incompleta"); DETALLES+=("faltan valores en $real: ${faltan% }")
      else
        ESTADOS+=("real"); DETALLES+=("$real")
        ARCHIVOS+=(--env-file "$real"); ACTIVAS+=("$nombre")
        while IFS= read -r linea; do POSTMAN+=("${linea#*Postman: }"); done \
          < <(grep -E '^# Postman:' "$plantilla" || true)
        while IFS= read -r linea; do PERFILES_EXTRA+=("${linea#*Perfil: }"); done \
          < <(grep -E '^# Perfil:' "$plantilla" || true)
        if [ "$nombre" = "ia" ] && [ -n "$(valor OLLAMA_MODEL_CI "$real")" ]; then
          MODELO="$(valor OLLAMA_MODEL_CI "$real")"
        fi
      fi
    fi
  done
}

actualizar() {
  [ "$ACTUALIZAR" -eq 1 ] || return 0
  info "${NEGRITA}Trayendo lo ultimo de origin/main...${NORMAL}"
  git pull --ff-only origin main || falla "No se pudo actualizar sin mezclar. Revisa 'git status'."
}

# ════════════════════════════════ MODO PRODUCCION ════════════════════════════════

aleatorio() {
  if command -v openssl >/dev/null; then openssl rand -hex "$1"
  else od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'; fi
}

hay_datos_prod() { docker volume inspect "${PROYECTO_PROD}_masssend_postgres_data" >/dev/null 2>&1; }

# Genera una sola vez los secretos internos; si faltan claves nuevas, solo agrega esas.
asegurar_secretos() {
  local clave nuevo
  if [ ! -f "$SECRETOS" ]; then
    hay_datos_prod && falla "Hay datos de produccion pero falta $SECRETOS, que tiene la clave de la base. Recuperalo o borra los datos con --borrar-datos."
    ( umask 077; printf '%s\n' "# Generado por levantar.sh. No lo borres ni lo compartas: la base usa esta clave." > "$SECRETOS" )
    info "Genere los secretos internos en $SECRETOS."
  fi
  for clave in SECRET_KEY JWT_SECRET_KEY POSTGRES_PASSWORD WHATSAPP_WEBHOOK_TOKEN \
               PB_SUPERUSER_EMAIL PB_SUPERUSER_PASSWORD ADMIN_EMAIL ADMIN_PASSWORD; do
    [ -z "$(valor "$clave" "$SECRETOS")" ] || continue
    case "$clave" in
      POSTGRES_PASSWORD) hay_datos_prod && falla "Falta POSTGRES_PASSWORD en $SECRETOS y la base ya existe. Recupera la clave o usa --borrar-datos."
                         nuevo=$(aleatorio 32) ;;
      PB_SUPERUSER_EMAIL|ADMIN_EMAIL) nuevo="admin@masssend.local" ;;
      PB_SUPERUSER_PASSWORD|ADMIN_PASSWORD) nuevo=$(aleatorio 16) ;;
      *) nuevo=$(aleatorio 32) ;;
    esac
    printf '%s=%s\n' "$clave" "$nuevo" >> "$SECRETOS"
  done
}

compose_prod() { docker compose -p "$PROYECTO_PROD" "${ARCHIVOS_PROD[@]}" --profile real "$@"; }

# Cualquier respuesta HTTP < 500 indica que gunicorn y Django arrancaron.
api_responde() {
  compose_prod exec -T backend python -c "import http.client as h; c=h.HTTPConnection('localhost',8000,timeout=3); c.request('GET','/api/v1/salud'); exit(0 if c.getresponse().status<500 else 1)" >/dev/null 2>&1
}

# El frontend responde y su proxy llega a la API.
web_responde() {
  compose_prod exec -T frontend wget -qO /dev/null http://127.0.0.1/api/v1/salud >/dev/null 2>&1
}

esperar_backend() {
  local intento
  for intento in $(seq 1 90); do
    api_responde && return 0
    sleep 2
  done
  return 1
}

estado_de() {
  local i
  for i in "${!NOMBRES[@]}"; do
    [ "${NOMBRES[$i]}" = "$1" ] && { printf '%s|%s' "${ESTADOS[$i]}" "${DETALLES[$i]}"; return; }
  done
  printf 'sin-archivo|'
}

informe_prod() {
  local estado detalle nombre i corriendo total caidos linea servicio situacion
  echo
  info "${NEGRITA}Estado de MassSend (produccion)${NORMAL}"

  if api_responde; then fila "API" "$VERDE" "lista" "http://localhost:${API_PORT}/api/v1/salud"
  else fila "API" "$ROJO" "no responde" "revisa: docker compose -p $PROYECTO_PROD logs backend"; fi

  if web_responde; then fila "Web" "$VERDE" "lista" "http://localhost:${FRONTEND_PORT}"
  else fila "Web" "$ROJO" "no responde" "revisa: docker compose -p $PROYECTO_PROD logs frontend"; fi

  IFS='|' read -r estado detalle <<< "$(estado_de gmail)"
  if [ "$estado" = "real" ]; then fila "Correos" "$VERDE" "Gmail" "llegan a los destinatarios reales"
  else fila "Correos" "$AMARILLO" "Mailpit" "http://localhost:${MAILPIT_PORT} (no salen a internet; $detalle)"; fi

  for nombre in "${NOMBRES[@]+"${NOMBRES[@]}"}"; do
    case "$nombre" in gmail|ia) continue ;; esac
    IFS='|' read -r estado detalle <<< "$(estado_de "$nombre")"
    case "$nombre" in google) etiqueta="Google" ;; paypal) etiqueta="PayPal" ;; payphone) etiqueta="PayPhone" ;; *) etiqueta="$nombre" ;; esac
    if [ "$estado" = "real" ]; then
      detalle=""
      if [ "$nombre" = "paypal" ]; then
        case "$(valor PAYPAL_BASE_URL backend/.env.paypal)" in ""|*sandbox*) detalle="Sandbox (dinero ficticio)" ;; esac
      fi
      [ "$nombre" = "payphone" ] && detalle="paga desde http://localhost:${FRONTEND_PORT}/creditos"
      fila "$etiqueta" "$VERDE" "activo" "$detalle"
    else
      fila "$etiqueta" "$AMARILLO" "no configurado" "$detalle"
    fi
  done

  if compose_prod exec -T ollama ollama list 2>/dev/null | grep -q "^${MODELO}"; then
    fila "Asistente" "$VERDE" "Ollama" "modelo $MODELO"
  else
    fila "Asistente" "$AMARILLO" "sin modelo" "se descarga al levantar ($MODELO)"
  fi

  if whatsapp_vinculado; then fila "WhatsApp" "$VERDE" "vinculado" "sesion guardada"
  else fila "WhatsApp" "$AMARILLO" "sin vincular" "escanea el QR con: ./levantar.sh --qr"; fi

  fila "Archivos" "$VERDE" "PocketBase" "interno"
  fila "Admin" "" "creado" "$(valor ADMIN_EMAIL "$SECRETOS") (clave: ADMIN_PASSWORD en $SECRETOS)"

  total=0; corriendo=0; caidos=""
  while IFS='|' read -r servicio situacion; do
    [ -n "$servicio" ] || continue
    total=$((total + 1))
    if [ "$situacion" = "running" ]; then corriendo=$((corriendo + 1)); else caidos+="$servicio($situacion) "; fi
  done < <(compose_prod ps -a --format '{{.Service}}|{{.State}}' 2>/dev/null || true)
  if [ "$total" -eq 0 ]; then fila "Servicios" "$AMARILLO" "apagados" "levanta con: ./levantar.sh"
  elif [ -z "$caidos" ]; then fila "Servicios" "$VERDE" "$corriendo/$total activos" ""
  else fila "Servicios" "$ROJO" "$corriendo/$total activos" "con problemas: $caidos"; fi

  if [ "${#ACTIVAS[@]}" -lt "${#NOMBRES[@]}" ]; then
    echo
    info "Para activar lo que falta, crea el archivo indicado y vuelve a ejecutar ./levantar.sh."
  fi
}

produccion() {
  detectar
  # Orden: secretos, ajustes opcionales y al final las integraciones (ganan).
  ARCHIVOS_PROD=()
  [ -f "$SECRETOS" ] && ARCHIVOS_PROD+=(--env-file "$SECRETOS")
  [ -f "$ENV_EXTRA" ] && ARCHIVOS_PROD+=(--env-file "$ENV_EXTRA")
  ARCHIVOS_PROD+=("${ARCHIVOS[@]+"${ARCHIVOS[@]}"}")

  case "$ACCION" in
    apagar|estado|qr)
      [ -f "$SECRETOS" ] || { info "Produccion nunca se ha levantado en este equipo. Ejecuta: ./levantar.sh"; return; } ;;
  esac
  case "$ACCION" in
    apagar) compose_prod down --remove-orphans
            info "Contenedores detenidos. Los datos se conservan; vuelve a levantar con ./levantar.sh"; return ;;
    estado) informe_prod; return ;;
    qr)     if whatsapp_vinculado; then info "WhatsApp ya esta vinculado; el registro muestra su estado."; fi
            info "Escanea el QR desde WhatsApp > Dispositivos vinculados. Sal con Ctrl+C."
            compose_prod logs -f --tail 60 whatsapp; return ;;
    borrar) aviso "Esto borra la base de datos, los archivos de PocketBase y los modelos de Ollama."
            printf 'Escribe BORRAR para confirmar: '
            local respuesta; read -r respuesta || true
            [ "$respuesta" = "BORRAR" ] || falla "Cancelado; no se borro nada."
            if [ -f "$SECRETOS" ]; then compose_prod down -v --remove-orphans
            else docker volume rm "${PROYECTO_PROD}_masssend_postgres_data" >/dev/null 2>&1 || true; fi
            info "Datos de produccion borrados."; return ;;
  esac

  asegurar_secretos
  [ "${ARCHIVOS_PROD[0]-}" = "--env-file" ] && [ "${ARCHIVOS_PROD[1]-}" = "$SECRETOS" ] \
    || ARCHIVOS_PROD=(--env-file "$SECRETOS" "${ARCHIVOS_PROD[@]+"${ARCHIVOS_PROD[@]}"}")

  if docker ps -q --filter "label=com.docker.compose.project=$PROYECTO" | grep -q .; then
    info "Apagando el modo prueba, que usa los mismos puertos..."
    docker compose -p "$PROYECTO" --env-file "$BASE_ENV" --profile ci --profile ia down -v --remove-orphans >/dev/null 2>&1 || true
  fi

  actualizar

  info "${NEGRITA}Construyendo y levantando MassSend (la primera vez tarda varios minutos)...${NORMAL}"
  compose_prod up --build -d --remove-orphans || falla "Docker Compose no pudo levantar los servicios."

  info "Esperando a que la API responda..."
  if ! esperar_backend; then
    aviso "La API no respondio. Ultimas lineas del registro:"
    compose_prod logs --tail 40 backend >&2 || true
    informe_prod
    exit 1
  fi

  # Crea el administrador la primera vez; si ya existe, no cambia nada.
  compose_prod exec -T backend python manage.py createsuperuser --noinput >/dev/null 2>&1 || true

  if ! compose_prod exec -T ollama ollama list 2>/dev/null | grep -q "^${MODELO}"; then
    info "Descargando el modelo de IA $MODELO (solo la primera vez)..."
    compose_prod exec -T ollama ollama pull "$MODELO" >/dev/null || aviso "No se pudo descargar $MODELO."
  fi

  informe_prod
  echo
  info "Apagar (conserva datos): ./levantar.sh --apagar   Ver estado: ./levantar.sh --estado"
}

# ═══════════════════════════════════ MODO PRUEBA ═══════════════════════════════════

mostrar_integraciones() {
  local i estado color
  info "${NEGRITA}Integraciones${NORMAL}"
  for i in "${!NOMBRES[@]}"; do
    case "${ESTADOS[$i]}" in
      real) estado="real"; color="$VERDE" ;;
      omitida) estado="omitida"; color="$AMARILLO" ;;
      incompleta) estado="simulada"; color="$AMARILLO" ;;
      *) estado="simulada"; color="" ;;
    esac
    printf '  %-8s %s%-10s%s %s\n' "${NOMBRES[$i]}" "$color" "$estado" "$NORMAL" "${DETALLES[$i]}"
  done
  [ "${#NOMBRES[@]}" -gt 0 ] || info "  (no hay plantillas backend/.env.*.example)"
}

prueba() {
  [ -f "$BASE_ENV" ] || falla "No encuentro $BASE_ENV. Ejecuta el script desde el repositorio."
  detectar
  ARCHIVOS=(--env-file "$BASE_ENV" "${ARCHIVOS[@]+"${ARCHIVOS[@]}"}")
  local perfil indicacion
  PERFILES=(--profile ci)
  for perfil in "${PERFILES_EXTRA[@]+"${PERFILES_EXTRA[@]}"}"; do
    [ "$perfil" = "ia" ] && IA=1 || PERFILES+=(--profile "$perfil")
  done
  [ "$IA" -eq 1 ] && PERFILES+=(--profile ia)
  compose() { docker compose -p "$PROYECTO" "${ARCHIVOS[@]}" "$@"; }

  case "$ACCION" in
    apagar) compose --profile ci --profile ia down -v --remove-orphans
            info "Contenedores detenidos y datos de prueba borrados."; return ;;
    estado) mostrar_integraciones; echo; compose --profile ci --profile ia ps; return ;;
  esac

  if docker ps -q --filter "label=com.docker.compose.project=$PROYECTO_PROD" | grep -q .; then
    falla "Produccion esta arriba y usa los mismos puertos. Apagala con: ./levantar.sh --apagar"
  fi

  actualizar

  mostrar_integraciones
  echo

  if [ "$IA" -eq 1 ]; then export GENERADOR_TEXTO_CI=ollama; fi

  if [ "$LIMPIO" -eq 1 ]; then
    info "Borrando la base de prueba anterior..."
    compose --profile ci --profile ia down -v --remove-orphans >/dev/null 2>&1 || true
  fi

  info "${NEGRITA}Construyendo y levantando (puede tardar la primera vez)...${NORMAL}"
  if ! compose "${PERFILES[@]}" up --build -d --wait --remove-orphans; then
    aviso "El backend no arranco. Ultimas lineas del registro:"
    compose "${PERFILES[@]}" logs --tail 40 backend-ci >&2 || true
    exit 1
  fi

  if [ "$IA" -eq 1 ]; then
    if ! compose "${PERFILES[@]}" exec -T ollama-ci ollama list 2>/dev/null | grep -q "^${MODELO}"; then
      info "Descargando el modelo $MODELO (solo la primera vez)..."
      compose "${PERFILES[@]}" exec -T ollama-ci ollama pull "$MODELO"
    fi
  fi

  echo
  info "${VERDE}${NEGRITA}MassSend (modo prueba) esta listo.${NORMAL}"
  info "  API:        http://localhost:${API_PORT}/api/v1/salud"
  if activa gmail; then info "  Correos:    llegan a tu Gmail"
  else info "  Correos:    http://localhost:${MAILPIT_PORT} (Mailpit)"; fi
  info "  Web:        http://localhost:${FRONTEND_PORT} (tambien abre ahi el url_pago de PayPhone)"
  info "  Asistente:  $([ "$IA" -eq 1 ] && echo "Ollama ($MODELO)" || echo "simulado (crea backend/.env.ia para Ollama)")"
  info "  Staff:      staff@prueba.local / clave-larga-123"
  echo
  info "${NEGRITA}En Postman (entorno MassSend local)${NORMAL}"
  [ "$API_PORT" = "8000" ] || info "  - baseUrl=http://localhost:${API_PORT}"
  [ "$MAILPIT_PORT" = "8025" ] || info "  - mailpitUrl=http://localhost:${MAILPIT_PORT}"
  for indicacion in "${POSTMAN[@]+"${POSTMAN[@]}"}"; do info "  - $indicacion"; done
  [ "${#POSTMAN[@]}" -gt 0 ] || info "  - deja los valores por defecto (todo simulado)"
  info "  - guarda el entorno con Ctrl+S antes de ejecutar"
  echo
  info "Apagar: ./levantar.sh --prueba --apagar   Empezar de cero: ./levantar.sh --prueba --limpio"
}

if [ "$MODO" = "produccion" ]; then produccion; else prueba; fi
