# MassSend

Plataforma para que los negocios lleguen a sus clientes por WhatsApp: gestiona contactos, lanza campañas personalizadas y mide resultados, con créditos prepagados y pagos en línea.

Este repositorio contiene el backend e implementa la arquitectura Onion. El frontend se incorporará en una fase posterior.

Desarrollado como proyecto de la asignatura **Arquitectura del Software**

**Universidad de las Fuerzas Armadas ESPE**
Sede Santo Domingo de los Tsáchilas  
**Docente:** Ing. Kevin Jair Chuquitanco Velasco 
**NRC:** 29888  
**Estudiante:** Anderson Lara, Carlos Calapucha

---

## Servicios

| Servicio | Función | Acceso |
|----------|---------|--------|
| `backend` | API Django, autenticación, campañas y pagos | http://localhost:8000 |
| `email-worker` | Cola de correos | Interno |
| `whatsapp` | Gateway Node.js con Baileys | Interno |
| `ollama` | Asistente de IA local | Interno |
| `pocketbase` | Archivos protegidos de campañas | Interno |
| `postgres` | Base de datos | Interno |

## Ejecución con Docker

Requiere Docker con Compose.

```bash
cp backend/.env.example backend/.env
```

Completa `backend/.env` con valores propios. Compose exige además `POSTGRES_PASSWORD`, `WHATSAPP_WEBHOOK_TOKEN`, `PB_SUPERUSER_EMAIL` y `PB_SUPERUSER_PASSWORD`. Ese archivo nunca se sube al repositorio.

```bash
docker compose --env-file backend/.env --profile real up --build -d
docker compose --env-file backend/.env --profile real exec backend python manage.py createsuperuser
```

El asistente de IA necesita descargar su modelo una sola vez:

```bash
docker compose --env-file backend/.env --profile real exec ollama ollama pull qwen2.5:0.5b
```

Para iniciar sesión se usa el nombre de usuario, no el correo, y se activa MFA con Google Authenticator.

## Pruebas

Se ejecutan en contenedores, desde `backend/`. Solo requieren Docker y `make`.

| Comando | Qué comprueba |
|---------|---------------|
| `make check` | Estilo, tipos, arquitectura y pruebas unitarias |
| `make test-legacy` | Pruebas del sistema actual |
| `make test-gateway` | Sintaxis del gateway, sin arrancarlo |
| `make test-int` | Integración con PostgreSQL temporal |
| `make e2e` | Colecciones de Postman con adaptadores falsos; requiere Postman CLI |

## API v1

La API se publica en `/api/v1/`. Para probarla en Postman sin WhatsApp, pagos ni correos reales:

```bash
docker compose -p masssend-ci --env-file backend/tests/ci.env --profile ci up --build -d
```

Importa `postman/environments/local.postman_environment.json` y las colecciones de `postman/collections/`. Los archivos de muestra están en `postman/archivos/`. La colección 05 corre una vez por arranque del perfil, porque activa el doble factor de la cuenta staff. Los correos capturados se ven en http://localhost:8025. Para apagar y borrar los datos de prueba:

```bash
docker compose -p masssend-ci --env-file backend/tests/ci.env --profile ci down -v
```

### Correos reales con Gmail

Por defecto los correos del perfil `ci` quedan en Mailpit. Para recibirlos en Gmail, copia `backend/.env.gmail.example` como `backend/.env.gmail`, completa tu cuenta y una contraseña de aplicación, y agrega ese archivo al comando:

```bash
docker compose -p masssend-ci --env-file backend/tests/ci.env --env-file backend/.env.gmail --profile ci up --build -d --wait
```

En el entorno de Postman cambia `modoCorreo` a `gmail` y escribe tu correo en `correoReal`. Los códigos se copian desde tu bandeja.

### Acceso con Google real

Por defecto el perfil `ci` usa un Google falso. Para entrar con tu cuenta de Google, crea en Google Cloud un ID de cliente OAuth de tipo *Aplicación web* con la URI de redireccionamiento `http://localhost:8000/api/v1/auth/google/callback`. Copia `backend/.env.google.example` como `backend/.env.google`, pega el ID y el secreto, y agrega ese archivo al comando (se puede combinar con `backend/.env.gmail`):

```bash
docker compose -p masssend-ci --env-file backend/tests/ci.env --env-file backend/.env.google --profile ci up --build -d --wait
```

En el entorno de Postman cambia `modoGoogle` a `google`. **Iniciar Google** devuelve una URL: ábrela en el navegador antes de 10 minutos y elige tu cuenta. El navegador muestra el siguiente paso y un `token_desafio`, con el que se continúa el doble factor en Postman. **Completar Google** se omite en este modo, porque Google entrega el código al navegador.

## Estructura

```
backend/
├── core/          configuración de Django
├── mass_sender/   contactos, campañas, envío, IA y archivos
├── email_auth/    verificación, recuperación y MFA
├── billing/       créditos y pagos
└── whatsapp_api/  gateway de WhatsApp
infra/pocketbase/  imagen del almacenamiento de archivos
compose.yaml       orquestación local
```

## Licencia

MIT. Consulta [LICENSE](./LICENSE).
