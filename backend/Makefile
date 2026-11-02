# Todo se ejecuta en contenedores: solo hace falta Docker y make.
IMAGEN := masssend-tests
GATEWAY := masssend-gateway-tests
INTEGRACION := docker compose -f tests/compose.yaml

.PHONY: imagen test test-int test-legacy test-gateway lint arch check e2e

imagen:
	docker build -q -f tests/Dockerfile -t $(IMAGEN) . > /dev/null

# Pruebas unitarias: sin base de datos ni red.
test: imagen
	docker run --rm --network none $(IMAGEN) pytest tests/unit

# Integración con PostgreSQL temporal; no toca los datos del proyecto.
test-int:
	$(INTEGRACION) run --rm --build pruebas; s=$$?; $(INTEGRACION) down -v; exit $$s

# Las pruebas del sistema actual.
test-legacy: imagen
	docker run --rm --network none $(IMAGEN)

# Revisa el gateway sin arrancarlo ni conectar WhatsApp.
test-gateway:
	docker build -q -f tests/Dockerfile.gateway -t $(GATEWAY) whatsapp_api > /dev/null
	docker run --rm --network none $(GATEWAY)

lint: imagen
	docker run --rm --network none $(IMAGEN) sh -c \
		"ruff check masssend tests && mypy masssend/domain masssend/application tests/fakes tests/unit"

arch: imagen
	docker run --rm --network none $(IMAGEN) lint-imports

check: lint arch test

# Requiere la API en ejecución y Postman CLI; las colecciones llegan en el Paso 4.
e2e:
	@ls ../postman/collections/*.json > /dev/null 2>&1 || \
		{ echo "Aun no hay colecciones en postman/collections."; exit 1; }
	@for c in ../postman/collections/*.json; do \
		postman collection run "$$c" -e ../postman/environments/local.postman_environment.json \
			|| exit 1; \
	done
