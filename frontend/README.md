# MassSend Frontend

Interfaz web de MassSend en React, Vite y Tailwind CSS. Consume solo la API v1 del backend (`/api/v1/`).

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
├── components/   ui (kit de Tailwind), auth, layout (menú lateral) y campanas
├── pages/        auth (pantallas sin sesión) y una página por módulo
└── modulos.js    menú lateral y accesos de Inicio
```

## Estilos

Todos los estilos usan Tailwind CSS v4 con el plugin oficial de Vite. Los colores de la marca (verde MassSend, fondo, burbujas de WhatsApp, PayPal y PayPhone) se definen una sola vez en el bloque `@theme` de `src/index.css` y se usan como `bg-marca`, `text-tinta`, `bg-chat`, etc.

Las piezas que se repiten viven en `src/components/ui/`: botones, tarjetas, insignias, campos, tablas, modales, estadísticas, pestañas y barras de progreso. Una pantalla nueva se arma con esas piezas y utilidades de Tailwind, sin hojas de estilo propias.
