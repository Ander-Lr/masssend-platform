"""Asistente: guia de la plataforma, saldo de la cuenta y redaccion de mensajes con IA."""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from masssend.application.ia.puertos import (
    EstadoGenerador,
    IGeneradorTexto,
    ISaldoCreditos,
    MensajeChat,
    SaldoCuenta,
)
from masssend.application.shared.puertos import IReloj
from masssend.domain.ia.consulta import Consulta, Turno
from masssend.domain.shared.identificadores import IdPublico

REDACCION = """Eres un redactor de mensajes de WhatsApp para campañas de MassSend.
Escribe SOLO el texto del mensaje, en español, listo para copiar: sin títulos, sin pasos, \
sin explicaciones, sin Markdown y sin hashtags. Máximo 60 palabras.
Empieza saludando con {{nombre}} (por ejemplo: Hola {{nombre}}), sé cordial y directo, \
incluye una llamada a la acción y usa uno o dos emojis."""

# Guia de uso de la plataforma: estas preguntas se responden con el texto tal cual.
# El modelo solo redacta mensajes; un modelo pequeno inventa pasos y datos.
SECCIONES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("campan", "enviar", "envio", "lanzar", "masivo", "plantilla", "adjunt"),
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
        ("contact", "import", "csv", "excel", "archivo", "etiquet", "telefon", "baja"),
        """Contactos, paso a paso:
1. Para uno solo: en Contactos pulsa "+ Agregar contacto" y escribe teléfono, nombre y etiquetas.
2. Para muchos: entra a Importar CSV y arrastra tu archivo .csv (máximo 5 MB).
3. El archivo lleva las columnas telefono, nombre, etiquetas y notas.
4. Pulsa "Vista previa e importar", revisa que cada columna esté bien asignada y pulsa "Importar".
Solo se aceptan móviles: en Ecuador 09XXXXXXXX y de otros países con su código.
Un contacto dado de baja no recibe campañas; si responde BAJA se da de baja solo.""",
    ),
    (
        ("credit", "saldo", "pago", "pagar", "comprar", "precio", "paypal", "payphone", "costo",
         "cuest"),
        """Créditos:
- 1 crédito = 1 mensaje enviado. Las cuentas nuevas reciben 10 créditos de bienvenida.
- Para comprar, entra a Créditos, elige un paquete (Básico 50 créditos por 2 USD, Estándar 150 \
por 5 USD o Pro 500 por 15 USD) y paga con PayPal o PayPhone. Al volver se acreditan solos.
- Al lanzar una campaña se reservan los créditos que necesita; si no alcanzan, no se puede lanzar.
- Si cancelas un envío, los créditos no usados se liberan.""",
    ),
    (
        ("segurid", "contrasen", "clave", "doble factor", "mfa", "totp", "google", "sesion",
         "mi cuenta", "registr", "verific"),
        """Cuenta y seguridad:
- Registro con nombre, correo y contraseña de al menos 8 caracteres; luego se verifica el correo \
con un código de 6 dígitos.
- También se puede entrar con Google.
- El doble factor con Google Authenticator es obligatorio para todas las cuentas.
- En Seguridad se cambia la contraseña; al hacerlo se cierran las sesiones abiertas.""",
    ),
    (
        ("whatsapp", "vincul", "conect", "qr", "chat"),
        """WhatsApp:
- El número de WhatsApp es de toda la plataforma y lo vincula una cuenta staff.
- En Conectar WhatsApp se escribe el número con código de país y se pide un código de 8 \
caracteres, que se escribe en el teléfono en WhatsApp, Dispositivos vinculados.
- Las cuentas staff también pueden conversar con los contactos en Chat.""",
    ),
    (
        ("report", "estadist", "historial", "entreg", "leido", "mensajes"),
        """Mensajes y reportes:
- En Mensajes está el historial de lo enviado y las respuestas recibidas, con filtros.
- En Reportes se ven enviados, entregados, leídos y fallidos por periodo, la actividad por día \
y las tasas de entrega y lectura.""",
    ),
)

TEMAS = """Puedo ayudarte con:
1. Crear y lanzar campañas.
2. Agregar o importar contactos.
3. Créditos: tu saldo, precios y compras.
4. Tu cuenta y la seguridad.
5. Conectar WhatsApp, mensajes y reportes.
6. Redactar el texto de una campaña, por ejemplo: \
"Redacta un mensaje para promocionar un descuento"."""

SALUDO = f"¡Hola! Soy el asistente de MassSend.\n{TEMAS}"
AGRADECIMIENTO = "¡Con gusto! Si necesitas algo más de MassSend, aquí estoy."
FUERA_DE_TEMA = f"Solo puedo ayudarte con el uso de MassSend.\n{TEMAS}"

SALUDOS = ("hola", "holi", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hey",
           "saludos", "que tal")
GRACIAS = ("gracias", "muchas gracias", "ok gracias", "genial", "perfecto", "listo")
PIDE_SALDO_TEMA = ("credit", "saldo")
PIDE_SALDO_PERSONAL = ("tengo", "me queda", "mi saldo", "disponible", "mis credit")
MODELO_CUENTA = "Tu cuenta"

PIDE_REDACCION = ("redact", "escrib", "crea un mensaje", "hazme un mensaje", "genera un mensaje",
                  "mensaje para", "texto para", "promocion", "anuncio")


MODELO_GUIA = "Guía de MassSend"

# Formas comunes de escribir WhatsApp. Las claves ya estan normalizadas.
SINONIMOS = {
    nombre: "whatsapp"
    for nombre in (
        "wasap", "wassap", "wasa", "wsp", "wpp", "whats", "whatsap", "watsap", "watsapp",
        "guasap", "guasa", "wapp", "wasapp", "whasapp", "whatapp", "whatssap",
    )
}
# Parecido minimo para aceptar una palabra mal escrita. Con 0.82 se aceptan errores
# como "camapaña" o "credtos" y se descartan palabras distintas como "segundo".
# Solo se compara por parecido con claves de 6 letras o mas: en las cortas, una letra
# distinta ya cambia la palabra ("cuenta" y "cuesta").
PARECIDO_MINIMO = 0.82
LARGO_MINIMO_PARECIDO = 6


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes, sin eñe ni signos: '¿Cómo me conecto?' -> 'como me conecto'."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^a-z0-9ñ ]+", " ", sin_tildes).split())


def _palabras(texto: str) -> list[str]:
    return [SINONIMOS.get(palabra, palabra) for palabra in normalizar(texto).split()]


def _coincide(palabra: str, clave: str) -> bool:
    """Prefijo exacto, o parecido suficiente si la clave es larga (tolera faltas)."""
    if palabra.startswith(clave):
        return True
    if len(clave) < LARGO_MINIMO_PARECIDO or len(palabra) < LARGO_MINIMO_PARECIDO - 1:
        return False
    return SequenceMatcher(None, palabra[: len(clave)], clave).ratio() >= PARECIDO_MINIMO


def menciones(texto: str, claves: tuple[str, ...]) -> int:
    """Cuantas claves aparecen en el texto. Las de varias palabras se buscan como frase."""
    palabras = _palabras(texto)
    frase = " ".join(palabras)
    return sum(
        (f" {clave} " in f" {frase} ")
        if " " in clave
        else any(_coincide(palabra, clave) for palabra in palabras)
        for clave in claves
    )


def pide_redaccion(pregunta: str) -> bool:
    pregunta_como = "como" in _palabras(pregunta)
    return menciones(pregunta, PIDE_REDACCION) > 0 and not pregunta_como


def tema_de(pregunta: str) -> str | None:
    """Seccion de la guia que responde la pregunta, o None si no trata de la plataforma."""
    puntajes = [(menciones(pregunta, claves), seccion) for claves, seccion in SECCIONES]
    mejor = max(puntaje for puntaje, _ in puntajes)
    if mejor == 0:
        return None
    return next(seccion for puntaje, seccion in puntajes if puntaje == mejor)


def pide_saldo(pregunta: str) -> bool:
    return menciones(pregunta, PIDE_SALDO_TEMA) > 0 and menciones(pregunta, PIDE_SALDO_PERSONAL) > 0


def es_cortesia(pregunta: str, frases: tuple[str, ...]) -> bool:
    """Un saludo o agradecimiento corto, sin otra pregunta."""
    texto = " ".join(_palabras(pregunta))
    if len(texto.split()) > 4:
        return False
    return any(
        texto.startswith(frase) or SequenceMatcher(None, texto, frase).ratio() >= 0.8
        for frase in frases
    )


def texto_saldo(saldo: SaldoCuenta) -> str:
    texto = f"Tienes {saldo.disponible} créditos disponibles."
    if saldo.reservado:
        texto += f" Además hay {saldo.reservado} reservados para campañas que se están enviando."
    if saldo.disponible == 0:
        texto += " Puedes comprar más en Créditos con PayPal o PayPhone."
    return texto


# Marcas de Markdown que un modelo pequeno agrega aunque se le pida texto simple.
_NEGRITA = re.compile(r"(\*\*|__)(.+?)\1")
_CURSIVA = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)\*(?!\w)")
_TITULO = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_VINETA = re.compile(r"^(\s*)[*+]\s+", re.MULTILINE)
_HASHTAGS_FINALES = re.compile(r"(?:\s+#[\w\u00C0-\u017F]+)+\s*$")
_FIN_DE_IDEA = (".", "!", "?", ":", ")")


def limpiar_respuesta(texto: str, completo: bool = True) -> str:
    """Quita el Markdown y, si el modelo corto a mitad, termina en la ultima idea completa."""
    limpio = _NEGRITA.sub(r"\2", texto)
    limpio = _CURSIVA.sub(r"\1", limpio)
    limpio = _TITULO.sub("", limpio)
    limpio = _VINETA.sub(r"\1- ", limpio).strip()
    limpio = _HASHTAGS_FINALES.sub("", limpio).strip()
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
    mensajes = [MensajeChat("system", REDACCION)]
    mensajes += [MensajeChat(turno.rol, turno.contenido) for turno in consulta.historial]
    mensajes.append(MensajeChat("user", consulta.pregunta))
    return mensajes


@dataclass(frozen=True, slots=True)
class RespuestaAsistente:
    respuesta: str
    modelo: str
    latencia_ms: int


class ConsultarAsistente:
    """Decide quien responde. El modelo solo redacta mensajes: en lo demas inventa."""

    def __init__(self, generador: IGeneradorTexto, reloj: IReloj, saldo: ISaldoCreditos) -> None:
        self._generador = generador
        self._reloj = reloj
        self._saldo = saldo

    def ejecutar(
        self, owner_id: IdPublico, pregunta: str, historial: list[Turno]
    ) -> RespuestaAsistente:
        consulta = Consulta.crear(pregunta, historial)
        texto = consulta.pregunta
        if pide_saldo(texto):
            return RespuestaAsistente(texto_saldo(self._saldo.saldo(owner_id)), MODELO_CUENTA, 0)
        if pide_redaccion(texto):
            return self._redactar(consulta)
        seccion = tema_de(texto)
        if seccion is not None:
            return RespuestaAsistente(seccion, MODELO_GUIA, 0)
        if es_cortesia(texto, GRACIAS):
            return RespuestaAsistente(AGRADECIMIENTO, MODELO_GUIA, 0)
        if es_cortesia(texto, SALUDOS):
            return RespuestaAsistente(SALUDO, MODELO_GUIA, 0)
        return RespuestaAsistente(FUERA_DE_TEMA, MODELO_GUIA, 0)

    def _redactar(self, consulta: Consulta) -> RespuestaAsistente:
        inicio = self._reloj.ahora()
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
