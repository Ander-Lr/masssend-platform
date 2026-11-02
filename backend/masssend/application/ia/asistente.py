"""Contexto y armado del mensaje, trasladados de mass_sender/ai_service.py."""

from dataclasses import dataclass

from masssend.application.ia.puertos import EstadoGenerador, IGeneradorTexto
from masssend.application.shared.puertos import IReloj
from masssend.domain.ia.consulta import Consulta, Turno

CONTEXTO_SISTEMA = """Eres el asistente virtual de MassSend, una plataforma web de envío masivo \
de mensajes de WhatsApp.
Responde SIEMPRE en español, de forma breve (máximo 120 palabras), clara y amable.

Conocimiento del sistema MassSend:
- Menú principal: Inicio, Chat, Campañas, Contactos, Importar CSV, Mensajes, Conectar WhatsApp, \
Notificaciones, Seguridad (MFA), Créditos y Asistente IA.
- Contactos: se importan desde un archivo CSV en "Importar CSV" y se organizan con etiquetas.
- Campañas: en "Campañas" se crea una campaña con nombre, plantilla de mensaje (admite variables \
como {{nombre}}), imagen o video opcional y filtro por etiquetas. Luego se ejecuta y los mensajes \
se envían por WhatsApp uno a uno en segundo plano.
- Conexión WhatsApp: en "Conectar WhatsApp" se escanea un código QR con el teléfono.
- Créditos: 1 crédito = 1 mensaje. Toda cuenta nueva recibe 10 créditos gratis; se compran más \
con PayPal o PayPhone en la página "Créditos". Sin saldo suficiente la campaña se bloquea.
- Seguridad: registro con verificación por correo, login con Google y verificación en dos pasos \
(MFA/TOTP) activable en "Seguridad".
- Reportes: entregas, lecturas y fallos por campaña (visible para administradores).

También puedes REDACTAR mensajes para campañas de WhatsApp si el usuario lo pide:
escribe mensajes cortos, cordiales y efectivos, usando la variable {{nombre}} para personalizar
y emojis con moderación. Entrega solo el texto del mensaje listo para copiar.

Si preguntan algo ajeno a MassSend o a la redacción de mensajes, indica amablemente
que solo puedes ayudar con el uso de la plataforma."""


def armar_prompt(consulta: Consulta) -> str:
    partes = [CONTEXTO_SISTEMA, ""]
    partes += [f"{turno.etiqueta}: {turno.contenido}" for turno in consulta.historial]
    partes += [f"Usuario: {consulta.pregunta}", "Asistente:"]
    return "\n".join(partes)


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
        generado = self._generador.generar(armar_prompt(consulta))
        latencia = self._reloj.ahora() - inicio
        return RespuestaAsistente(
            generado.texto.strip(), generado.modelo, round(latencia.total_seconds() * 1000)
        )


class RevisarAsistente:
    def __init__(self, generador: IGeneradorTexto) -> None:
        self._generador = generador

    def ejecutar(self) -> EstadoGenerador:
        return self._generador.estado()
