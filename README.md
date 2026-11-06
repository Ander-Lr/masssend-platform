# MassSend

Plataforma para que los negocios lleguen a sus clientes por WhatsApp: gestiona contactos, lanza campañas personalizadas y mide resultados, con créditos prepagados y pagos en línea.

Este repositorio contiene el backend, construido con arquitectura Onion y diseño guiado por el dominio (DDD). El frontend se incorporará en una fase posterior.

Desarrollado como proyecto de la asignatura **Arquitectura del Software**

**Universidad de las Fuerzas Armadas ESPE**
Sede Santo Domingo de los Tsáchilas
**Docente:** Ing. Kevin Jair Chuquitanco Velasco
**NRC:** 29888
**Estudiantes:** Anderson Lara, Carlos Calapucha

---

## Contenido

1. [Prerrequisitos](#1-prerrequisitos)
2. [Inicio rápido](#2-inicio-rápido)
3. [Probar la API con Postman](#3-probar-la-api-con-postman)
4. [Integraciones reales opcionales](#4-integraciones-reales-opcionales)
5. [Sistema completo con WhatsApp](#5-sistema-completo-con-whatsapp)
6. [Pruebas automatizadas](#6-pruebas-automatizadas)
7. [Solución de problemas](#7-solución-de-problemas)
8. [Estructura del proyecto](#8-estructura-del-proyecto)

---

## 1. Prerrequisitos

Todo el proyecto corre en contenedores, así que no hace falta instalar Python, Node.js ni PostgreSQL en el equipo.

| Herramienta | Versión mínima | Uso | Obligatoria |
|-------------|----------------|-----|-------------|
| Git | 2.30 | Clonar el repositorio | Sí |
| Docker Engine o Docker Desktop | 24 | Ejecutar los contenedores | Sí |
| Docker Compose | v2.24 (comando `docker compose`) | Orquestar los servicios | Sí |
| Bash 4 (Linux/macOS) o PowerShell 5.1 (Windows) | — | Ejecutar `levantar.sh` o `levantar.cmd` | Sí |
| Postman Desktop | 10 | Probar la API manualmente | Recomendada |
| GNU make | 4 | Ejecutar las pruebas automatizadas | Opcional |
| Postman CLI | 1.x | Ejecutar `make e2e` | Opcional |

Recursos del equipo: al menos 4 GB de RAM libres para Docker y 5 GB de disco. Si se activa el asistente de IA, se necesitan unos 400 MB más para el modelo.

Puertos que deben estar libres en el equipo:

| Puerto | Servicio |
|--------|----------|
| 8000 | API (`http://localhost:8000/api/v1/`) |
| 8025 | Mailpit, bandeja de correos de prueba |
| 5173 | Página local de pagos |

Si alguno está ocupado, se puede cambiar con las variables `API_PORT`, `MAILPIT_PORT` y `FRONTEND_PORT` (ver la sección 7).

### Según el sistema operativo

- **Linux:** instala Docker Engine y el plugin de Compose desde la documentación oficial de Docker. Agrega tu usuario al grupo `docker` (`sudo usermod -aG docker $USER`) y vuelve a iniciar sesión.
- **macOS:** instala Docker Desktop. Bash ya viene incluido.
- **Windows:** instala Docker Desktop con el backend WSL 2 y déjalo abierto. Desde PowerShell o CMD usa `.\levantar.cmd` con las mismas opciones que `levantar.sh` (no hace falta cambiar la política de ejecución). También puedes usar `levantar.sh` desde WSL o Git Bash; `.gitattributes` fija los saltos de línea de cada script al clonar.

Comprueba que todo esté instalado:

```bash
git --version
docker --version
docker compose version
```

---

## 2. Inicio rápido

Este modo levanta la API con adaptadores simulados: WhatsApp, pagos, Google y el asistente de IA se simulan, y los correos se capturan en Mailpit. No necesita ninguna cuenta ni clave.

**Paso 1. Clonar el repositorio**

```bash
git clone https://github.com/Ander-Lr/masssend-platform.git
cd masssend-platform
```

**Paso 2. Dar permiso de ejecución al script (solo Linux, macOS y WSL)**

```bash
chmod +x levantar.sh
```

**Paso 3. Levantar el proyecto en modo prueba**

```bash
./levantar.sh --prueba          # Linux, macOS, WSL
.\levantar.cmd --prueba         # Windows (PowerShell o CMD)
```

Sin `--prueba` el script levanta el sistema en producción (sección 5).

La primera vez tarda varios minutos porque descarga las imágenes y construye el backend. Al terminar, el script muestra las direcciones de la API, de Mailpit y de la página de pagos, junto con la cuenta staff de prueba.

**Paso 4. Comprobar que la API responde**

Abre en el navegador `http://localhost:8000/api/v1/salud` o ejecuta:

```bash
curl http://localhost:8000/api/v1/salud
```

La respuesta debe indicar que la base de datos y la caché están operativas.

**Paso 5. Apagar**

```bash
./levantar.sh --prueba --apagar
```

La base de datos de prueba vive en memoria, así que al apagar se borran todos los datos.

### Opciones del script

En Windows se usan las mismas opciones con `.\levantar.cmd`.

| Comando | Qué hace |
|---------|----------|
| `./levantar.sh --prueba` | Construye lo que cambió y levanta el modo prueba |
| `./levantar.sh --prueba --limpio` | Borra la base de prueba y empieza de cero |
| `./levantar.sh --prueba --ia` | Agrega el asistente de IA con Ollama |
| `./levantar.sh --prueba --sin paypal` | Ignora una integración aunque esté configurada |
| `./levantar.sh --prueba --actualizar` | Trae lo último de `origin/main` antes de levantar |
| `./levantar.sh --prueba --estado` | Muestra los contenedores y las integraciones detectadas |
| `./levantar.sh --prueba --apagar` | Detiene todo y borra los datos de prueba |
| `./levantar.sh --ayuda` | Muestra la ayuda completa |

### Sin el script

El mismo entorno se levanta directamente con Compose:

```bash
docker compose -p masssend-ci --env-file backend/tests/ci.env --profile ci up --build -d --wait
docker compose -p masssend-ci --env-file backend/tests/ci.env --profile ci down -v
```

---

## 3. Probar la API con Postman

1. Abre Postman e importa el entorno `postman/environments/local.postman_environment.json`.
2. Importa las cinco colecciones de `postman/collections/`.
3. Selecciona el entorno **MassSend local** en la esquina superior derecha.
4. Ejecuta las colecciones en orden, de la 01 a la 05.

| Colección | Módulo |
|-----------|--------|
| 01 | Identidad: registro, verificación, inicio de sesión y doble factor |
| 02 | Créditos: saldo, compras y pagos |
| 03 | Contactos y campañas |
| 04 | Envío de campañas |
| 05 | Asistente de IA y notificaciones |

Notas:

- Los archivos de muestra que usan las colecciones están en `postman/archivos/`. Si Postman no los encuentra, configura esa carpeta como directorio de trabajo en *Settings > General > Working directory*.
- Los códigos de verificación llegan a Mailpit (`http://localhost:8025`) y las colecciones los leen solas.
- La colección 05 se ejecuta una vez por arranque, porque activa el doble factor de la cuenta staff. Para repetirla, usa `./levantar.sh --prueba --limpio`.
- Cuenta staff de prueba: `staff@prueba.local` con clave `clave-larga-123`. Solo existe en este entorno.
- Para el doble factor se usa Google Authenticator o cualquier aplicación TOTP.

---

## 4. Integraciones reales opcionales

Cada integración tiene una plantilla `backend/.env.<nombre>.example`. Para activarla, se copia como `backend/.env.<nombre>`, se completan sus valores y se vuelve a ejecutar el script, que la detecta y la carga sola. Los mismos archivos sirven en producción (`./levantar.sh`) y en modo prueba (`./levantar.sh --prueba`). Esos archivos nunca se suben al repositorio.

```bash
cp backend/.env.gmail.example backend/.env.gmail
# editar backend/.env.gmail con tus valores
./levantar.sh --prueba
```

El script indica al final qué variables hay que cambiar en el entorno de Postman. Después de cambiarlas, guarda el entorno con Ctrl+S.

| Integración | Plantilla | Qué se necesita | Variable de Postman |
|-------------|-----------|-----------------|---------------------|
| Correos reales | `.env.gmail.example` | Cuenta de Gmail y una contraseña de aplicación | `modoCorreo=gmail`, `correoReal` |
| Acceso con Google | `.env.google.example` | Cliente OAuth de Google Cloud | `modoGoogle=google` |
| PayPal Sandbox | `.env.paypal.example` | App de PayPal Developer en modo Sandbox | `modoPago=paypal` |
| PayPhone pruebas | `.env.payphone.example` | App WEB de Payphone Developer en ambiente de pruebas | `modoPayphone=payphone` |
| Asistente de IA | `.env.ia.example` | Nada, el modelo se descarga solo | Ninguna |

### Correos con Gmail

1. Activa la verificación en dos pasos en tu cuenta de Google.
2. Genera una contraseña de aplicación en `https://myaccount.google.com/apppasswords`.
3. Completa `EMAIL_USER` y `EMAIL_APP_PASSWORD` (16 letras, sin espacios) en `backend/.env.gmail`.
4. En Postman cambia `modoCorreo` a `gmail` y escribe tu correo en `correoReal`. Los códigos se copian desde tu bandeja.

### Acceso con Google

1. En Google Cloud crea un ID de cliente OAuth de tipo *Aplicación web*.
2. Agrega la URI de redireccionamiento `http://localhost:8000/api/v1/auth/google/callback`.
3. Pega el ID y el secreto en `backend/.env.google`.
4. En Postman cambia `modoGoogle` a `google`. La petición **Iniciar Google** devuelve una URL que se abre en el navegador antes de 10 minutos. El navegador muestra un `token_desafio` con el que se continúa el doble factor en Postman. La petición **Completar Google** se omite en este modo.

### PayPal Sandbox

1. En `https://developer.paypal.com` crea una app en modo Sandbox.
2. Pega el Client ID y el Secret en `backend/.env.paypal`.
3. En Postman cambia `modoPago` a `paypal`. La petición **Checkout** devuelve la URL de PayPal. Ábrela, paga con la cuenta *Personal* de Sandbox y luego ejecuta **Confirmar**.
4. Al terminar, PayPal redirige a `localhost:5173`. Mientras no exista el frontend esa página puede no cargar, y eso no afecta al pago.

Las peticiones **Pago rechazado** y **Cobro por otro monto** se omiten en este modo, porque PayPal no acepta respuestas simuladas.

### PayPhone

1. En Payphone Developer crea una aplicación **WEB** en ambiente **PRUEBAS** con la URL de respuesta `http://localhost:5173/billing/return?provider=payphone`.
2. Pega el token y el StoreID de la pestaña *Credenciales* en `backend/.env.payphone`.
3. En Postman cambia `modoPayphone` a `payphone` y usa la carpeta **PayPhone** de la colección 02.
4. **Checkout PayPhone** guarda en `urlPagoLocal` la dirección que debes abrir. Después de pagar, la página muestra el `id`. Cópialo en `payphoneId` y ejecuta **Confirmar PayPhone** antes de 5 minutos, porque si no se confirma a tiempo PayPhone revierte el cobro.

Cada pasarela se activa por separado: activar PayPhone no vuelve real a PayPal.

### Asistente de IA con Ollama

```bash
cp backend/.env.ia.example backend/.env.ia
./levantar.sh --prueba
```

También se puede activar solo por una vez con `./levantar.sh --prueba --ia`. La primera vez se descarga el modelo `qwen2.5:0.5b`. Por su tamaño reducido, el modelo puede dar respuestas imprecisas.

---

## 5. Sistema completo con WhatsApp

El perfil `real` levanta todos los servicios con integraciones reales, incluido el gateway de WhatsApp.

| Servicio | Función | Acceso |
|----------|---------|--------|
| `backend` | API Django | `http://localhost:8000` |
| `envio-worker` | Procesa la cola de envíos de campañas | Interno |
| `email-worker` | Procesa la cola de correos | Interno |
| `whatsapp` | Gateway Node.js con Baileys | Interno |
| `ollama` | Asistente de IA local | Interno |
| `pocketbase` | Archivos protegidos de campañas | Interno |
| `postgres` | Base de datos | Interno |
| `redis` | Caché y límites de peticiones | Interno |

Es el modo por defecto del script y no necesita configuración previa:

```bash
./levantar.sh          # Linux, macOS, WSL
.\levantar.cmd         # Windows (PowerShell o CMD)
```

Qué hace por ti:

- La primera vez genera los secretos internos (base de datos, firma de tokens, PocketBase y administrador) en `backend/.env.secretos`. Ese archivo no se sube al repositorio y **no debe borrarse** mientras existan los datos, porque la base quedó creada con esa clave.
- Usa los archivos de integración que existan (`backend/.env.gmail`, `.env.google`, `.env.paypal`, `.env.payphone`, `.env.ia`), igual que el modo prueba.
- Espera a que la API responda, crea el administrador `admin@masssend.local` y descarga el modelo de IA la primera vez.
- Al final informa el estado de cada parte:

| Parte | Con su archivo | Sin su archivo |
|-------|----------------|----------------|
| Correos | Salen por Gmail | Se quedan en Mailpit (`http://localhost:8025`) |
| Google, PayPal, PayPhone | Activos | "No configurado": esa función responde con error y nunca se simula |
| Asistente de IA | Modelo de `.env.ia` | Ollama con `qwen2.5:0.5b` |
| WhatsApp | — | Pide vincularlo con `./levantar.sh --qr` |

La clave del administrador está en `ADMIN_PASSWORD` dentro de `backend/.env.secretos`. `backend/.env` es opcional y solo sirve para ajustes extra, como `ALLOWED_HOSTS` o `FRONTEND_URL`.

| Comando | Qué hace |
|---------|----------|
| `./levantar.sh` | Levanta o actualiza producción e informa el estado |
| `./levantar.sh --estado` | Informa el estado sin levantar nada |
| `./levantar.sh --qr` | Muestra el código QR para vincular WhatsApp (*Dispositivos vinculados*) |
| `./levantar.sh --sin paypal` | Deja una integración sin usar aunque exista su archivo |
| `./levantar.sh --apagar` | Detiene todo y conserva los datos |
| `./levantar.sh --borrar-datos` | Borra base, archivos y modelos (pide escribir `BORRAR`) |

El modo prueba y producción usan los mismos puertos. Al levantar producción, el script apaga el modo prueba si estaba arriba; al revés, te pide apagar producción primero.

---

## 6. Pruebas automatizadas

Se ejecutan en contenedores desde la carpeta `backend/` y solo requieren Docker y `make`.

```bash
cd backend
make check
```

| Comando | Qué comprueba |
|---------|---------------|
| `make check` | Estilo, tipos, contratos de arquitectura y pruebas unitarias |
| `make test` | Solo las pruebas unitarias de dominio y aplicación |
| `make arch` | Que ningún anillo dependa de uno exterior |
| `make test-int` | Integración con un PostgreSQL temporal |
| `make test-gateway` | Sintaxis del gateway de WhatsApp, sin arrancarlo |
| `make e2e` | Las cinco colecciones de Postman con adaptadores simulados, requiere Postman CLI |

---

## 7. Solución de problemas

| Problema | Solución |
|----------|----------|
| `permission denied` al ejecutar `./levantar.sh` | Ejecuta `chmod +x levantar.sh` o usa `bash levantar.sh` |
| `no se puede cargar ... levantar.ps1` en Windows | Usa `.\levantar.cmd`, que omite la política de ejecución |
| Una función aparece como "no configurado" | Crea el archivo que indica el informe y vuelve a ejecutar `./levantar.sh` |
| `Hay datos de produccion pero falta backend/.env.secretos` | Recupera ese archivo; si los datos no importan, `./levantar.sh --borrar-datos` |
| `bad interpreter` o `\r: command not found` en Windows | El archivo se clonó con saltos de línea de Windows. Ejecuta `git config --global core.autocrlf input`, borra la carpeta y vuelve a clonar |
| `permission denied` al conectar con Docker en Linux | Agrega tu usuario al grupo `docker` y vuelve a iniciar sesión |
| `port is already allocated` | Apaga el otro modo o cambia el puerto: `API_PORT=8080 ./levantar.sh` (Windows: `$env:API_PORT="8080"`), y actualiza `baseUrl` en Postman |
| El backend no arranca | El script muestra las últimas líneas del registro. Para verlo completo: `docker compose -p masssend-ci logs backend-ci` |
| Datos de pruebas anteriores interfieren | `./levantar.sh --prueba --limpio` |
| La colección 05 falla en la segunda ejecución | Es esperado, porque el doble factor de la cuenta staff ya se activó. Usa `./levantar.sh --prueba --limpio` |
| Una integración aparece como simulada | `./levantar.sh --prueba --estado` indica qué valores faltan en su archivo |
| El asistente responde con texto simulado | Crea `backend/.env.ia` o ejecuta `./levantar.sh --prueba --ia` |

---

## 8. Estructura del proyecto

```
backend/
├── masssend/
│   ├── domain/           entidades, objetos de valor, reglas y puertos de repositorio
│   ├── application/      casos de uso y puertos
│   ├── infrastructure/   repositorios ORM, adaptadores y composición
│   └── interfaces/       API REST, webhooks y workers
├── config/               configuración de Django
├── tests/                pruebas unitarias, de integración y dobles de prueba
└── whatsapp_api/         gateway de WhatsApp
infra/
├── pocketbase/           imagen del almacenamiento de archivos
└── pasarela-local/       página local para los pagos de PayPhone
postman/
├── collections/          colecciones 01 a 05
├── environments/         entorno local
└── archivos/             archivos de muestra
compose.yaml              orquestación con los perfiles real, ci e ia
levantar.sh               arranque en un solo paso (producción o --prueba)
levantar.cmd, .ps1        equivalente para Windows
```

Los módulos de negocio son `identidad`, `creditos`, `ia`, `campanas` y `envio`, más `shared` para lo común. Cada uno existe dentro de cada anillo, y el núcleo (`domain` y `application`) solo usa la biblioteca estándar de Python.

## Licencia

MIT. Consulta [LICENSE](./LICENSE).
