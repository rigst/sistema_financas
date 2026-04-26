from decimal import Decimal, InvalidOperation

from .validators import somente_digitos


def calcular_expressao_decimal_br(valor, default=None):
    if valor in (None, ""):
        return default

    if isinstance(valor, Decimal):
        return valor

    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if not texto:
        return default

    def parse_numero(item):
        item = item.strip()
        if not item:
            raise ValueError("Valor decimal inválido.")
        if "," in item and "." in item:
            item = item.replace(".", "").replace(",", ".")
        elif "," in item:
            item = item.replace(",", ".")
        elif "." in item:
            partes = item.split(".")
            if len(partes) > 1 and all(len(parte) == 3 for parte in partes[1:]):
                item = "".join(partes)
        try:
            return Decimal(item)
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Valor decimal inválido.")

    tokens = []
    atual = ""
    espera_numero = True
    for caractere in texto:
        if caractere.isdigit() or caractere in ",.":
            atual += caractere
            espera_numero = False
            continue
        if caractere in "+-" and espera_numero:
            atual += caractere
            espera_numero = False
            continue
        if caractere in "+-*/()":
            if atual:
                tokens.append(parse_numero(atual))
                atual = ""
            if caractere == "(":
                tokens.append(caractere)
                espera_numero = True
            elif caractere == ")":
                tokens.append(caractere)
                espera_numero = False
            else:
                tokens.append(caractere)
                espera_numero = True
            continue
        raise ValueError("Valor decimal inválido.")

    if atual:
        tokens.append(parse_numero(atual))
    if not tokens:
        raise ValueError("Valor decimal inválido.")

    def aplicar_operador(valores, operador):
        if len(valores) < 2:
            raise ValueError("Valor decimal inválido.")
        direita = valores.pop()
        esquerda = valores.pop()
        if operador == "+":
            valores.append(esquerda + direita)
        elif operador == "-":
            valores.append(esquerda - direita)
        elif operador == "*":
            valores.append(esquerda * direita)
        elif operador == "/":
            if direita == 0:
                raise ValueError("Valor decimal inválido.")
            valores.append(esquerda / direita)
        else:
            raise ValueError("Valor decimal inválido.")

    precedencia = {"+": 1, "-": 1, "*": 2, "/": 2}
    valores = []
    operadores = []

    for token in tokens:
        if isinstance(token, Decimal):
            valores.append(token)
        elif token == "(":
            operadores.append(token)
        elif token == ")":
            while operadores and operadores[-1] != "(":
                aplicar_operador(valores, operadores.pop())
            if not operadores or operadores[-1] != "(":
                raise ValueError("Valor decimal inválido.")
            operadores.pop()
        else:
            while operadores and operadores[-1] != "(" and precedencia[operadores[-1]] >= precedencia[token]:
                aplicar_operador(valores, operadores.pop())
            operadores.append(token)

    while operadores:
        operador = operadores.pop()
        if operador == "(":
            raise ValueError("Valor decimal inválido.")
        aplicar_operador(valores, operador)

    if len(valores) != 1:
        raise ValueError("Valor decimal inválido.")
    return valores[0]


def parse_decimal_br(valor, default=None):
    try:
        return calcular_expressao_decimal_br(valor, default=default)
    except ValueError:
        raise


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
