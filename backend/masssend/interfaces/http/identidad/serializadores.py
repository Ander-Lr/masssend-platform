"""Solo validan el formato; las reglas viven en el dominio."""

from rest_framework import serializers


class Registro(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    correo = serializers.CharField(max_length=254)
    contrasena = serializers.CharField(max_length=128, trim_whitespace=False)


class Verificar(serializers.Serializer):
    correo = serializers.CharField(max_length=254)
    codigo = serializers.CharField(max_length=6)


class Correo(serializers.Serializer):
    correo = serializers.CharField(max_length=254)


class Login(serializers.Serializer):
    correo = serializers.CharField(max_length=254)
    contrasena = serializers.CharField(max_length=128, trim_whitespace=False)


class LoginTotp(serializers.Serializer):
    token_desafio = serializers.CharField(max_length=128)
    codigo = serializers.CharField(max_length=8)


class Renovacion(serializers.Serializer):
    renovacion = serializers.CharField(max_length=2048)


class Restablecer(serializers.Serializer):
    token = serializers.CharField(max_length=128)
    nueva_contrasena = serializers.CharField(max_length=128, trim_whitespace=False)


class CambiarContrasena(serializers.Serializer):
    contrasena_actual = serializers.CharField(max_length=128, trim_whitespace=False)
    nueva_contrasena = serializers.CharField(max_length=128, trim_whitespace=False)


class ActivarMfa(serializers.Serializer):
    token_desafio = serializers.CharField(max_length=128, required=False)


class ConfirmarMfa(ActivarMfa):
    codigo = serializers.CharField(max_length=8)


class DesactivarMfa(serializers.Serializer):
    contrasena = serializers.CharField(max_length=128, trim_whitespace=False)


class GoogleCallback(serializers.Serializer):
    state = serializers.CharField(max_length=128)
    code = serializers.CharField(max_length=2048)
