#!/usr/bin/env bash
# Levanta MassSend (perfil ci) con todas las integraciones reales que tengas configuradas.
#
# Uso: ./levantar.sh [opciones]
#   (sin opciones)    reconstruye lo que cambio y levanta todo; si ya estaba arriba,
#                     conserva los datos de prueba
#   -l, --limpio      borra la base de prueba antes de levantar (empieza de cero)
#   -i, --ia          agrega Ollama (perfil ia) y descarga el modelo si falta
#   -s, --sin NOMBRE  no usa una integracion aunque exista (ej. --sin paypal); se repite
#   -a, --actualizar  trae lo ultimo de origin/main (git pull --ff-only) antes de levantar
#       --apagar      detiene todo; la base de prueba vive en memoria y se borra
#       --estado      muestra los contenedores y las integraciones detectadas
#   -h, --ayuda       muestra esta ayuda
#
# Integraciones: cada backend/.env.<nombre>.example es una integracion. Si existe
# backend/.env.<nombre> con sus valores completos, se carga sola. Para agregar una
# nueva solo se crea su plantilla .example; este script no cambia. En la plantilla:
#   "# Postman: ..."      indica que variables cambiar en el entorno de Postman
#   "# Opcional. ..."     encima de una variable permite dejarla vacia
#
# Variables: PROYECTO (masssend-ci), API_PORT (8000), MAILPIT_PORT (8025).
# Nunca imprime los valores de los archivos .env.
# La base de prueba (postgres-ci) vive en memoria: se pierde al apagar.

set -euo pipefail
cd "$(dirname "$0")"

PROYECTO="${PROYECTO:-masssend-ci}"
export API_PORT="${API_PORT:-8000}"
export MAILPIT_PORT="${MAILPIT_PORT:-8025}"
BASE_ENV="backend/tests/ci.env"
MODELO="${OLLAMA_MODEL_CI:-qwen2.5:0.5b}"

if [ -t 1 ]; then
  VERDE=$'\e[32m'; AMARILLO=$'\e[33m'; ROJO=$'\e[31m'; NEGRITA=$'\e[1m'; NORMAL=$'\e[0m'
else
  VERDE=""; AMARILLO=""; ROJO=""; NEGRITA=""; NORMAL=""
fi
info() { printf '%s\n' "$*"; }
aviso() { printf '%s! %s%s\n' "$AMARILLO" "$*" "$NORMAL"; }
falla() { printf '%sX %s%s\n' "$ROJO" "$*" "$NORMAL" >&2; exit 1; }

ayuda() { sed -n '2,/^$/p' "$0" | sed -E 's/^# ?//'; }

ACCION="levantar"; LIMPIO=0; IA=0; ACTUALIZAR=0; EXCLUIDAS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -l|--limpio) LIMPIO=1 ;;
    -i|--ia) IA=1 ;;
    -a|--actualizar) ACTUALIZAR=1 ;;
    -s|--sin) [ $# -ge 2 ] || falla "--sin necesita un nombre, por ejemplo: --sin paypal"
              EXCLUIDAS+=("$2"); shift ;;
    --apagar) ACCION="apagar" ;;
    --estado) ACCION="estado" ;;
    -h|--ayuda) ayuda; exit 0 ;;
    *) falla "Opcion desconocida: $1 (usa --ayuda)" ;;
  esac
  shift
done

command -v docker >/dev/null || falla "Docker no esta instalado."
docker compose version >/dev/null 2>&1 || falla "Falta Docker Compose v2 (docker compose)."
[ -f "$BASE_ENV" ] || falla "No encuentro $BASE_ENV. Ejecuta el script desde el repositorio."

# Lee el valor de una variable sin ejecutar el archivo (no hace source).
valor() {
  local linea
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

ARCHIVOS=(--env-file "$BASE_ENV"); ACTIVAS=(); RESUMEN=(); POSTMAN=()
detectar() {
  local plantilla nombre real faltan
  for plantilla in backend/.env.*.example; do
    [ -e "$plantilla" ] || continue
    nombre="${plantilla#backend/.env.}"; nombre="${nombre%.example}"
    real="backend/.env.$nombre"
    if excluida "$nombre"; then
      RESUMEN+=("$nombre|${AMARILLO}omitida${NORMAL}|pediste --sin $nombre")
    elif [ ! -f "$real" ]; then
      RESUMEN+=("$nombre|simulada|crea $real desde $plantilla")
    else
      faltan=$(faltantes "$plantilla" "$real")
      if [ -n "$faltan" ]; then
        RESUMEN+=("$nombre|${AMARILLO}simulada${NORMAL}|faltan valores en $real: ${faltan% }")
      else
        ARCHIVOS+=(--env-file "$real"); ACTIVAS+=("$nombre")
        RESUMEN+=("$nombre|${VERDE}real${NORMAL}|$real")
        while IFS= read -r linea; do POSTMAN+=("${linea#*Postman: }"); done \
          < <(grep -E '^# Postman:' "$plantilla" || true)
      fi
    fi
  done
}

mostrar_integraciones() {
  local fila nombre estado detalle
  info "${NEGRITA}Integraciones${NORMAL}"
  for fila in "${RESUMEN[@]+"${RESUMEN[@]}"}"; do
    IFS='|' read -r nombre estado detalle <<< "$fila"
    printf '  %-8s %-18s %s\n' "$nombre" "$estado" "$detalle"
  done
  [ "${#RESUMEN[@]}" -gt 0 ] || info "  (no hay plantillas backend/.env.*.example)"
}

detectar
PERFILES=(--profile ci)
[ "$IA" -eq 1 ] && PERFILES+=(--profile ia)
compose() { docker compose -p "$PROYECTO" "${ARCHIVOS[@]}" "$@"; }

case "$ACCION" in
  apagar) compose --profile ci --profile ia down -v --remove-orphans
          info "Contenedores detenidos y datos de prueba borrados."; exit 0 ;;
  estado) mostrar_integraciones; echo; compose --profile ci --profile ia ps; exit 0 ;;
esac

if [ "$ACTUALIZAR" -eq 1 ]; then
  info "${NEGRITA}Trayendo lo ultimo de origin/main...${NORMAL}"
  git pull --ff-only origin main || falla "No se pudo actualizar sin mezclar. Revisa 'git status'."
fi

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
info "${VERDE}${NEGRITA}MassSend esta listo.${NORMAL}"
info "  API:        http://localhost:${API_PORT}/api/v1/salud"
if [[ " ${ACTIVAS[*]-} " == *" gmail "* ]]; then
  info "  Correos:    llegan a tu Gmail"
else
  info "  Correos:    http://localhost:${MAILPIT_PORT} (Mailpit)"
fi
info "  Asistente:  $([ "$IA" -eq 1 ] && echo "Ollama ($MODELO)" || echo "simulado (usa --ia para Ollama)")"
info "  Staff:      staff@prueba.local / clave-larga-123"
echo
info "${NEGRITA}En Postman (entorno MassSend local)${NORMAL}"
[ "$API_PORT" = "8000" ] || info "  - baseUrl=http://localhost:${API_PORT}"
[ "$MAILPIT_PORT" = "8025" ] || info "  - mailpitUrl=http://localhost:${MAILPIT_PORT}"
for indicacion in "${POSTMAN[@]+"${POSTMAN[@]}"}"; do info "  - $indicacion"; done
[ "${#POSTMAN[@]}" -gt 0 ] || info "  - deja los valores por defecto (todo simulado)"
info "  - guarda el entorno con Ctrl+S antes de ejecutar"
echo
info "Apagar: ./levantar.sh --apagar   Empezar de cero: ./levantar.sh --limpio"
