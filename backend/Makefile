# Todo se ejecuta en contenedores: solo hace falta Docker y make.
IMAGEN := masssend-tests
GATEWAY := masssend-gateway-tests
INTEGRACION := docker compose -f tests/compose.yaml
API_PORT ?= 8000
CI := API_PORT=$(API_PORT) docker compose -p masssend-ci -f ../compose.yaml \
	--env-file tests/ci.env --profile ci $(COMPOSE_EXTRA)

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
		"ruff check config masssend tests && mypy masssend/domain masssend/application tests/fakes tests/unit"

arch: imagen
	docker run --rm --network none $(IMAGEN) lint-imports

check: lint arch test

# Levanta el perfil ci, corre las colecciones de Postman y lo apaga todo.
# Requiere Postman CLI. Tiene su propio proyecto: nunca toca los datos reales.
e2e:
	@$(CI) up --build -d --wait --wait-timeout 180; \
	s=$$?; \
	if [ $$s = 0 ]; then \
		for c in ../postman/collections/*.json; do \
			postman collection run "$$c" \
				-e ../postman/environments/local.postman_environment.json \
				--env-var "baseUrl=http://localhost:$(API_PORT)" \
				--working-dir ../postman || { s=1; break; }; \
		done; \
	fi; \
	$(CI) down -v > /dev/null 2>&1; exit $$s
