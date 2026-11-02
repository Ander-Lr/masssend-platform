# Servicio WhatsApp de MassSend (Node + Baileys).
# Baileys se conecta por WebSocket directo a WhatsApp: NO necesita
# Chromium ni Puppeteer (eso era de la versión antigua con whatsapp-web.js).
FROM node:20-slim

# git es necesario porque Baileys instala una dependencia desde GitHub
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY index.js .

EXPOSE 3001

CMD ["node", "index.js"]
