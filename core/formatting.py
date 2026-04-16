from decimal import Decimal, InvalidOperation

from .validators import somente_digitos


def parse_decimal_br(valor, default=None):
    if valor in (None, ""):
        return default

    if isinstance(valor, Decimal):
        return valor

    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if not texto:
        return default

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return Decimal(texto)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Valor decimal inválido.")


def formatar_decimal_br(valor, casas=2):
    numero = parse_decimal_br(valor, default=Decimal("0")) or Decimal("0")
    mascara = f"{{:,.{casas}f}}"
    return mascara.format(numero).replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_moeda_br(valor):
    return f"R$ {formatar_decimal_br(valor, casas=2)}"


def formatar_cpf_cnpj_br(valor):
    digitos = somente_digitos(valor)
    if len(digitos) <= 11:
        digitos = digitos[:11]
        if len(digitos) <= 3:
            return digitos
        if len(digitos) <= 6:
            return f"{digitos[:3]}.{digitos[3:]}"
        if len(digitos) <= 9:
            return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:]}"
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"

    digitos = digitos[:14]
    if len(digitos) <= 2:
        return digitos
    if len(digitos) <= 5:
        return f"{digitos[:2]}.{digitos[2:]}"
    if len(digitos) <= 8:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:]}"
    if len(digitos) <= 12:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:]}"
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


def formatar_telefone_br(valor):
    digitos = somente_digitos(valor)[:11]
    if len(digitos) <= 2:
        return digitos
    if len(digitos) <= 6:
        return f"({digitos[:2]}) {digitos[2:]}"
    if len(digitos) <= 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"


def formatar_cep_br(valor):
    digitos = somente_digitos(valor)[:8]
    if len(digitos) <= 5:
        return digitos
    return f"{digitos[:5]}-{digitos[5:]}"
