# Imagen solo para pruebas del backend. No se despliega.
# Desde backend/ se usa con make check, make test-int y make test-legacy.
#
# La orden por defecto ejecuta las pruebas del sistema actual:
#   docker build -f tests/Dockerfile -t masssend-tests .
#   docker run --rm masssend-tests
FROM python:3.11-slim

# Dependencias del sistema (para psycopg2)
RUN apt-get update && apt-get install -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --default-timeout=120 --retries=10 --no-cache-dir \
    -r requirements.txt -r requirements-dev.txt

COPY . .

# Valores falsos: Django los exige para iniciar y solo existen en esta imagen.
ENV SECRET_KEY=solo-pruebas \
    JWT_SECRET_KEY=solo-pruebas \
    DEBUG=True

# El contenedor termina con error si cualquiera de las tres revisiones falla.
CMD ["sh", "-c", "python manage.py check && python manage.py makemigrations --check --dry-run && python manage.py test"]
