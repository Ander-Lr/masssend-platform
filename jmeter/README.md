# Pruebas de carga con JMeter

`carga-contactos-campanas.jmx` mide cómo responde la API cuando varios usuarios usan a la vez los endpoints de contactos, campañas y envío.

## Qué hace

1. **Preparar cuenta de prueba** (un solo hilo, al inicio):
   - registra una cuenta;
   - lee el código de verificación del correo (en el perfil `ci` los correos llegan a Mailpit);
   - activa el doble factor, calculando el código TOTP con un script;
   - compra créditos con la pasarela de prueba;
   - comparte el token con los hilos de carga.
2. **Usuarios usando contactos y campañas**: cada hilo repite estas peticiones, con una pausa de 0,2 a 0,6 s entre una y otra.
   - crea un contacto;
   - lista contactos, busca por texto y consulta el contacto creado;
   - crea una campaña para ese contacto, la lanza y consulta su progreso;
   - lista mensajes y pide el reporte.

Cada petición falla si no devuelve el código esperado o si tarda más de `maxms` milisegundos.

## Requisitos

- **JMeter 5.6** o superior, que necesita **Java 17**.
- El **perfil `ci`** levantado. Este perfil usa WhatsApp, pagos y correo de prueba, y sube los límites de peticiones para que no corten la medición.

```bash
docker compose -p masssend-ci --env-file backend/tests/ci.env --profile ci up --build -d --wait
```

No lo corras contra el perfil `real`, porque enviaría mensajes de WhatsApp de verdad.

## Ejecución

Desde la raíz del repositorio, sin interfaz gráfica, que es como se mide la carga:

```bash
jmeter -n -t jmeter/carga-contactos-campanas.jmx -l jmeter/resultados/resultados.jtl -e -o jmeter/resultados/reporte -f
```

Al terminar, abre `jmeter/resultados/reporte/index.html`. La carpeta `jmeter/resultados/` no se sube al repositorio.

Para ver o editar el plan, ábrelo con `jmeter.bat` (Windows) o `jmeter` (Linux y macOS).

## Parámetros

Se cambian con `-J`, por ejemplo `-Jhilos=25 -Jduracion=180`.

| Parámetro | Por defecto | Qué controla |
|---|---|---|
| `hilos` | 10 | Usuarios simultáneos |
| `rampa` | 10 | Segundos en que arrancan todos los hilos |
| `duracion` | 60 | Segundos de carga. Debe ser menor a 900, porque el token dura 15 minutos |
| `paquetes` | 4 | Paquetes Pro de 500 créditos que se compran. Cada vuelta gasta 1 crédito |
| `maxms` | 2000 | Tiempo máximo aceptado por petición |
| `host`, `puerto` | localhost, 8000 | Dónde está la API |
| `mailpit` | http://localhost:8025 | Dónde leer el código de verificación |

Si en una prueba larga `POST /campanas/{id}/lanzar` empieza a responder 402, se acabaron los créditos: sube `paquetes`.
