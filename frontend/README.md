# MassSend Frontend

Interfaz web de MassSend en React y Vite. Consume solo la API v1 del backend (`/api/v1/`).

## Desarrollo

Requiere Node.js 20 o superior y el backend levantado en `http://localhost:8000`.

```bash
cd frontend
npm install
npm run dev
```

La app queda en `http://localhost:3000`. Vite reenvía `/api` al backend, así que no hace falta configurar CORS.

| Variable | Valor por defecto | Uso |
|----------|-------------------|-----|
| `VITE_PUERTO` | `3000` | Puerto del servidor de desarrollo |
| `VITE_API_DESTINO` | `http://localhost:8000` | Dirección del backend |

Para el acceso con Google, la URI de redireccionamiento autorizada en Google Cloud y `GOOGLE_RETORNO_V1` deben apuntar a `http://localhost:3000/auth/google/callback`.

## Comandos

| Comando | Qué hace |
|---------|----------|
| `npm run dev` | Servidor de desarrollo con recarga automática |
| `npm run lint` | Revisa el código con ESLint |
| `npm run build` | Genera la versión de producción en `dist/` |

## Estructura

```
src/
├── api/          cliente HTTP de la v1 y un archivo por módulo
├── context/      sesión, tokens JWT y doble factor
├── components/   auth (tarjetas y formularios) y layout (menú lateral)
├── pages/        auth (pantallas sin sesión) y una página por módulo
└── modulos.js    menú lateral y accesos de Inicio
```
