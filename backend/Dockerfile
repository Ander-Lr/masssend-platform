FROM python:3.11-slim

# Dependencias del sistema (para psycopg2)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --default-timeout=120 --retries=10 --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

ENV DEBUG=False

# Variables dummy solo para este RUN: no quedan en la imagen, así un
# despliegue sin secretos reales falla en vez de arrancar con los dummy.
RUN SECRET_KEY=dummy-build-only JWT_SECRET_KEY=dummy-build-only python manage.py collectstatic --noinput

# Puerto
EXPOSE 8000

# Script de arranque
COPY entrypoint.sh /entrypoint.sh
# Quitar finales de línea de Windows (CRLF) para que Linux pueda ejecutarlo
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
