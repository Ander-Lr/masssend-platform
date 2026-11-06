# Frontend de MassSend en dos etapas:
# 1) Node compila React y Tailwind con Vite.
# 2) Nginx sirve los archivos y reenvia /api al backend, asi el navegador ve un solo origen.
FROM node:22-alpine AS compilacion
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# La plantilla se completa al arrancar con API_DESTINO (por ejemplo http://backend:8000).
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=compilacion /app/dist /usr/share/nginx/html
ENV API_DESTINO=http://backend:8000
EXPOSE 80
HEALTHCHECK --interval=5s --timeout=3s --retries=20 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
