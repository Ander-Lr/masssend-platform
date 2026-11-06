// Endpoints del modulo identidad: registro, sesion, doble factor y recuperacion.
import { get, post } from './cliente'

const publica = { publica: true }

// Registro y verificacion
export const registrar = (nombre, correo, contrasena) =>
  post('auth/registro', { nombre, correo, contrasena }, publica)
export const verificar = (correo, codigo) => post('auth/verificar', { correo, codigo }, publica)
export const reenviarCodigo = correo => post('auth/reenviar-codigo', { correo }, publica)

// Inicio de sesion: la contrasena nunca entrega tokens, siempre devuelve el siguiente paso
export const iniciarSesion = (correo, contrasena) => post('auth/login', { correo, contrasena }, publica)
export const validarTotp = (tokenDesafio, codigo) =>
  post('auth/login/totp', { token_desafio: tokenDesafio, codigo }, publica)
export const cerrarSesion = renovacion => post('auth/logout', { renovacion })
export const perfil = () => get('auth/yo')

// Google
export const urlGoogle = () => get('auth/google', null, publica)
export const completarGoogle = (state, code) => get('auth/google/callback', { state, code }, publica)

// Recuperacion de contrasena
export const solicitarRecuperacion = correo => post('auth/recuperar', { correo }, publica)
export const restablecer = (token, nuevaContrasena) =>
  post('auth/restablecer', { token, nueva_contrasena: nuevaContrasena }, publica)
export const cambiarContrasena = (actual, nueva) =>
  post('auth/cambiar-contrasena', { contrasena_actual: actual, nueva_contrasena: nueva })

// Doble factor. Con tokenDesafio se usa durante el enrolamiento, sin JWT.
export const activarMfa = tokenDesafio =>
  post('mfa/activar', tokenDesafio ? { token_desafio: tokenDesafio } : {}, tokenDesafio ? publica : undefined)
export const confirmarMfa = (codigo, tokenDesafio) =>
  post(
    'mfa/confirmar',
    tokenDesafio ? { codigo, token_desafio: tokenDesafio } : { codigo },
    tokenDesafio ? publica : undefined,
  )
export const estadoMfa = () => get('mfa/estado')
export const desactivarMfa = contrasena => post('mfa/desactivar', { contrasena })
