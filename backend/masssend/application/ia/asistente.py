"""Contexto y armado del mensaje, trasladados de mass_sender/ai_service.py."""

import re
from dataclasses import dataclass

from masssend.application.ia.puertos import EstadoGenerador, IGeneradorTexto, MensajeChat
from masssend.application.shared.puertos import IReloj
from masssend.domain.ia.consulta import Consulta, Turno

# Guia de uso de la plataforma. Las preguntas sobre estos temas se responden con este
# texto tal cual; el modelo solo redacta mensajes y conversa (un modelo pequeno inventa pasos).
REGLAS = """Eres el asistente virtual de MassSend, una plataforma web para enviar mensajes \
masivos y personalizados por WhatsApp.
Responde SIEMPRE en español, breve (máximo 90 palabras), clara y amable.
Escribe en texto simple: sin Markdown, sin asteriscos, sin almohadillas y sin enlaces.
Usa solo la información de abajo. Si no está ahí, dilo; no inventes pasos, botones ni enlaces."""

REDACCION = """Eres un redactor de mensajes de WhatsApp para campañas de MassSend.
Escribe SOLO el texto del mensaje, en español, listo para copiar: sin títulos, sin pasos, \
sin explicaciones y sin Markdown. Máximo 60 palabras.
Empieza saludando con {{nombre}} (por ejemplo: Hola {{nombre}}), sé cordial y directo, \
incluye una llamada a la acción y usa uno o dos emojis."""

SECCIONES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("campaña", "campana", "enviar", "envio", "lanzar", "masivo", "plantilla", "adjunt"),
        """Crear y enviar una campaña, paso a paso:
1. Entra a Campañas y pulsa "+ Nueva campaña".
2. Escribe el nombre y el mensaje. Usa {{nombre}} para poner el nombre de cada contacto.
3. Elige las etiquetas de destinatarios. Sin etiquetas se envía a todos los contactos activos.
4. Si quieres, adjunta una imagen (JPG, PNG o WEBP hasta 5 MB) o un video MP4 hasta 16 MB.
5. Pulsa "Crear campaña". Queda como borrador.
6. Pulsa "Lanzar": verás los destinatarios y tus créditos. Confirma.
7. El progreso se ve en vivo y puedes cancelar el envío; los créditos no usados se liberan.
Los mensajes salen uno a uno con pausas para cuidar el número de WhatsApp.""",
    ),
    (
        ("contacto", "importar", "csv", "excel", "archivo", "etiqueta", "telefono", "teléfono",
         "baja", "lista"),
        """Contactos, paso a paso:
1. Para uno solo: en Contactos pulsa "+ Agregar contacto" y escribe teléfono, nombre y etiquetas.
2. Para muchos: entra a Importar CSV y arrastra tu archivo .csv (máximo 5 MB).
3. El archivo lleva las columnas telefono, nombre, etiquetas y notas.
4. Pulsa "Vista previa e importar", revisa que cada columna esté bien asignada y pulsa "Importar".
Solo se aceptan móviles: en Ecuador 09XXXXXXXX y de otros países con su código.
Un contacto dado de baja no recibe campañas; si responde BAJA se da de baja solo.""",
    ),
    (
        ("credito", "crédito", "saldo", "pago", "pagar", "comprar", "precio", "paypal",
         "payphone", "costo", "cuesta"),
        """Créditos:
- 1 crédito = 1 mensaje enviado. Las cuentas nuevas reciben 10 créditos de bienvenida.
- Para comprar, entra a Créditos, elige un paquete (Básico 50 créditos por 2 USD, Estándar 150 \
por 5 USD o Pro 500 por 15 USD) y paga con PayPal o PayPhone. Al volver se acreditan solos.
- Al lanzar una campaña se reservan los créditos que necesita; si no alcanzan, no se puede lanzar.
- Si cancelas un envío, los créditos no usados se liberan.""",
    ),
    (
        ("seguridad", "contraseña", "contrasena", "clave", "doble factor", "mfa", "totp",
         "google", "sesion", "sesión", "cuenta", "registr", "correo"),
        """Cuenta y seguridad:
- Registro con nombre, correo y contraseña de al menos 8 caracteres; luego se verifica el correo \
con un código de 6 dígitos.
- También se puede entrar con Google.
- El doble factor con Google Authenticator es obligatorio para todas las cuentas.
- En Seguridad se cambia la contraseña; al hacerlo se cierran las sesiones abiertas.""",
    ),
    (
        ("whatsapp", "vincular", "conectar", "numero", "número", "qr", "chat"),
        """WhatsApp:
- El número de WhatsApp es de toda la plataforma y lo vincula una cuenta staff.
- En Conectar WhatsApp se escribe el número con código de país y se pide un código de 8 \
caracteres, que se escribe en el teléfono en WhatsApp, Dispositivos vinculados.
- Las cuentas staff también pueden conversar con los contactos en Chat.""",
    ),
    (
        ("reporte", "estadistic", "estadístic", "mensajes", "historial", "entreg", "leido",
         "leído", "respuesta"),
        """Mensajes y reportes:
- En Mensajes está el historial de lo enviado y las respuestas recibidas, con filtros.
- En Reportes se ven enviados, entregados, leídos y fallidos por periodo, la actividad por día \
y las tasas de entrega y lectura.""",
    ),
)

GENERAL = """MassSend sirve para enviar campañas de WhatsApp personalizadas.
Menú: Inicio, Campañas, Contactos, Importar CSV, Mensajes, Reportes, Créditos, Asistente IA y \
Seguridad. Las cuentas staff ven además Chat, Conectar WhatsApp, Notificaciones y Cola de correos.
Puedes preguntar cómo crear una campaña, importar contactos, comprar créditos o pedir que \
redacte un mensaje.
Si preguntan algo ajeno a MassSend, di amablemente que solo puedes ayudar con la plataforma."""

PIDE_REDACCION = ("redact", "escrib", "crea un mensaje", "hazme un mensaje", "genera un mensaje",
                  "mensaje para", "texto para", "promocion", "promoción", "promociona", "anuncio")


MODELO_GUIA = "Guía de MassSend"


def pide_redaccion(pregunta: str) -> bool:
    texto = pregunta.lower()
    pregunta_como = "cómo" in texto or "como " in texto
    return any(clave in texto for clave in PIDE_REDACCION) and not pregunta_como


def tema_de(pregunta: str) -> str | None:
    """Seccion de la guia que responde la pregunta, o None si no trata de la plataforma."""
    texto = pregunta.lower()
    puntajes = [(sum(clave in texto for clave in claves), seccion) for claves, seccion in SECCIONES]
    mejor = max(puntaje for puntaje, _ in puntajes)
    if mejor == 0:
        return None
    return next(seccion for puntaje, seccion in puntajes if puntaje == mejor)


def contexto_para(pregunta: str) -> str:
    """Instrucciones de sistema para el modelo: redactar o conversar con el resumen general."""
    if pide_redaccion(pregunta):
        return REDACCION
    return f"{REGLAS}\n\n{GENERAL}"


# Marcas de Markdown que un modelo pequeno agrega aunque se le pida texto simple.
_NEGRITA = re.compile(r"(\*\*|__)(.+?)\1")
_CURSIVA = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)\*(?!\w)")
_TITULO = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_VINETA = re.compile(r"^(\s*)[*+]\s+", re.MULTILINE)
_FIN_DE_IDEA = (".", "!", "?", ":", ")")


def limpiar_respuesta(texto: str, completo: bool = True) -> str:
    """Quita el Markdown y, si el modelo corto a mitad, termina en la ultima idea completa."""
    limpio = _NEGRITA.sub(r"\2", texto)
    limpio = _CURSIVA.sub(r"\1", limpio)
    limpio = _TITULO.sub("", limpio)
    limpio = _VINETA.sub(r"\1- ", limpio).strip()
    if completo or not limpio:
        return limpio
    lineas = limpio.split("\n")
    if len(lineas) > 1:
        # La ultima linea quedo a medias: se descarta entera.
        return "\n".join(lineas[:-1]).rstrip()
    corte = max(limpio.rfind(signo) for signo in _FIN_DE_IDEA)
    return limpio[: corte + 1] if corte > 0 else limpio


def armar_mensajes(consulta: Consulta) -> list[MensajeChat]:
    # Las instrucciones van en su propio rol: en un solo texto, un modelo
    # pequeno las confunde con la pregunta y responde cosas como "SI.".
    mensajes = [MensajeChat("system", contexto_para(consulta.pregunta))]
    mensajes += [MensajeChat(turno.rol, turno.contenido) for turno in consulta.historial]
    mensajes.append(MensajeChat("user", consulta.pregunta))
    return mensajes


@dataclass(frozen=True, slots=True)
class RespuestaAsistente:
    respuesta: str
    modelo: str
    latencia_ms: int


class ConsultarAsistente:
    def __init__(self, generador: IGeneradorTexto, reloj: IReloj) -> None:
        self._generador = generador
        self._reloj = reloj

    def ejecutar(self, pregunta: str, historial: list[Turno]) -> RespuestaAsistente:
        consulta = Consulta.crear(pregunta, historial)
        inicio = self._reloj.ahora()
        # El uso de la plataforma se responde con la guia: un modelo pequeno inventa pasos.
        seccion = None if pide_redaccion(consulta.pregunta) else tema_de(consulta.pregunta)
        if seccion is not None:
            return RespuestaAsistente(seccion, MODELO_GUIA, 0)
        generado = self._generador.generar(armar_mensajes(consulta))
        latencia = self._reloj.ahora() - inicio
        return RespuestaAsistente(
            limpiar_respuesta(generado.texto, generado.completo),
            generado.modelo,
            round(latencia.total_seconds() * 1000),
        )


class RevisarAsistente:
    def __init__(self, generador: IGeneradorTexto) -> None:
        self._generador = generador

    def ejecutar(self) -> EstadoGenerador:
        return self._generador.estado()
