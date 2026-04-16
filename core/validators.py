import re

from django.core.exceptions import ValidationError


UF_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def validar_cpf_cnpj_basico(valor: str, *, tipo_pessoa: str | None = None):
    if not valor:
        return

    digitos = somente_digitos(valor)
    if len(digitos) not in {11, 14}:
        raise ValidationError("Informe um CPF com 11 dígitos ou um CNPJ com 14 dígitos.")

    if tipo_pessoa == "PF" and len(digitos) != 11:
        raise ValidationError("Para pessoa física, informe um CPF com 11 dígitos.")

    if tipo_pessoa == "PJ" and len(digitos) != 14:
        raise ValidationError("Para pessoa jurídica, informe um CNPJ com 14 dígitos.")


def validar_telefone_basico(valor: str, *, campo: str):
    if not valor:
        return

    digitos = somente_digitos(valor)
    if len(digitos) < 10 or len(digitos) > 11:
        raise ValidationError(f"{campo} deve ter 10 ou 11 dígitos, incluindo DDD.")


def validar_cep_basico(valor: str):
    if not valor:
        return

    digitos = somente_digitos(valor)
    if len(digitos) != 8:
        raise ValidationError("CEP deve ter 8 dígitos.")


def validar_uf(valor: str):
    if not valor:
        return

    uf = valor.strip().upper()
    if uf not in UF_VALIDAS:
        raise ValidationError("Informe uma UF válida com duas letras.")
