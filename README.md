# MassSend

Plataforma para que los negocios lleguen a sus clientes por WhatsApp: gestiona contactos, lanza campañas personalizadas y mide resultados, con créditos prepagados y pagos en línea.

Este repositorio contiene el backend e implementa la arquitectura Onion. El frontend se incorporará en una fase posterior.

Desarrollado como proyecto de la asignatura **Arquitectura del Software**

**Universidad de las Fuerzas Armadas ESPE**
Sede Santo Domingo de los Tsáchilas  
**Docente:** Ing. Kevin Jair Chuquitanco Velasco 
**NRC:** 29888  
**Estudiante:** Anderson Lenin Lara Chicaiza

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
docker compose --env-file backend/.env up --build -d
docker compose --env-file backend/.env exec backend python manage.py createsuperuser
```

El asistente de IA necesita descargar su modelo una sola vez:

```bash
docker compose --env-file backend/.env exec ollama ollama pull qwen2.5:0.5b
```

Para iniciar sesión se usa el nombre de usuario, no el correo, y se activa MFA con Google Authenticator.

## Pruebas

```bash
docker compose --env-file backend/.env exec backend python manage.py test
```

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
