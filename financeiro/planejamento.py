from datetime import timedelta
from decimal import Decimal

from .models import Despesa, Receita, adicionar_meses_data, arredondar


def inicio_da_semana(data_base):
    return data_base - timedelta(days=data_base.weekday())


def fim_da_semana(data_base):
    return inicio_da_semana(data_base) + timedelta(days=6)


def inicio_do_mes(data_base):
    return data_base.replace(day=1)


def fim_do_mes(data_base):
    proximo_mes = adicionar_meses_data(inicio_do_mes(data_base), 1)
    return proximo_mes - timedelta(days=1)


def navegacao_semanal(referencia):
    inicio = inicio_da_semana(referencia)
    return {
        "referencia": referencia,
        "inicio": inicio,
        "fim": inicio + timedelta(days=6),
        "anterior": inicio - timedelta(days=7),
        "proxima": inicio + timedelta(days=7),
    }


def _semanas_do_mes(referencia):
    inicio_mes = inicio_do_mes(referencia)
    fim_mes = fim_do_mes(referencia)
    inicio = inicio_da_semana(inicio_mes)
    semanas = []
    while inicio <= fim_mes:
        semanas.append((inicio, inicio + timedelta(days=6)))
        inicio += timedelta(days=7)
    return semanas


def _somar_ocorrencias(ocorrencias, *, filtro=None):
    itens = ocorrencias if filtro is None else [item for item in ocorrencias if filtro(item)]
    return arredondar(sum((item["valor"] for item in itens), Decimal("0.00")))


def receitas_no_periodo(user, inicio, fim):
    ocorrencias = []
    for receita in Receita.objects.filter(criado_por=user, ativa=True).prefetch_related("recebimentos"):
        for ocorrencia in receita.ocorrencias(inicio, fim):
            ocorrencias.append({"receita": receita, **ocorrencia})
    return ocorrencias


def despesas_no_periodo(user, inicio, fim):
    ocorrencias = []
    for despesa in Despesa.objects.filter(criado_por=user).exclude(status="cancelada").prefetch_related("pagamentos"):
        for ocorrencia in despesa.ocorrencias(inicio, fim):
            ocorrencias.append({"despesa": despesa, **ocorrencia})
    return ocorrencias


def _filtrar_por_data(ocorrencias, inicio, fim):
    return [item for item in ocorrencias if inicio <= item["data"] <= fim]


def resumo_fluxo_periodo(user, inicio, fim):
    receitas = receitas_no_periodo(user, inicio, fim)
    despesas = despesas_no_periodo(user, inicio, fim)
    receitas_recebidas = _somar_ocorrencias(receitas, filtro=lambda item: item["status"] == "recebida")
    receitas_previstas = _somar_ocorrencias(receitas, filtro=lambda item: item["status"] == "prevista")
    fixos = _somar_ocorrencias(despesas, filtro=lambda item: item["despesa"].tipo == "fixa")
    parcelas = _somar_ocorrencias(despesas, filtro=lambda item: item["despesa"].tipo == "parcelada")
    variaveis = _somar_ocorrencias(despesas, filtro=lambda item: item["despesa"].tipo == "variavel")
    despesas_pagas = _somar_ocorrencias(despesas, filtro=lambda item: item["status"] == "paga")
    despesas_pendentes = _somar_ocorrencias(despesas, filtro=lambda item: item["status"] == "pendente")
    variaveis_pagas = _somar_ocorrencias(despesas, filtro=lambda item: item["despesa"].tipo == "variavel" and item["status"] == "paga")
    variaveis_pendentes = _somar_ocorrencias(despesas, filtro=lambda item: item["despesa"].tipo == "variavel" and item["status"] == "pendente")
    despesas_total = arredondar(fixos + parcelas + variaveis)
    receitas_total = arredondar(receitas_recebidas + receitas_previstas)
    return {
        "inicio": inicio,
        "fim": fim,
        "receitas": receitas,
        "despesas": despesas,
        "receitas_total": receitas_total,
        "receitas_recebidas": receitas_recebidas,
        "receitas_previstas": receitas_previstas,
        "fixos": fixos,
        "parcelas": parcelas,
        "variaveis": variaveis,
        "variaveis_pagas": variaveis_pagas,
        "variaveis_pendentes": variaveis_pendentes,
        "despesas_pagas": despesas_pagas,
        "despesas_pendentes": despesas_pendentes,
        "despesas_total": despesas_total,
        "saldo_planejado": arredondar(receitas_total - despesas_total),
        "saldo_confirmado": arredondar(receitas_recebidas - despesas_pagas),
    }


def _receitas_confirmadas_ate(receitas_mes, data_limite):
    return _somar_ocorrencias(
        receitas_mes,
        filtro=lambda item: item["status"] == "recebida" and (item["data_recebimento"] or item["data"]) <= data_limite,
    )


def _data_fluxo_receita(item):
    return item["data_recebimento"] or item["data"]


def _saldo_total_confirmado(user, referencia):
    inicio = adicionar_meses_data(inicio_do_mes(referencia), -60)
    fim = referencia
    receitas = receitas_no_periodo(user, inicio, fim)
    despesas = despesas_no_periodo(user, inicio, fim)
    receitas_confirmadas = _receitas_confirmadas_ate(receitas, fim)
    despesas_ate_hoje = _somar_ocorrencias(despesas, filtro=lambda item: item["status"] == "paga" and item["data"] <= fim)
    return arredondar(receitas_confirmadas - despesas_ate_hoje)


def calcular_planejamento_semanal(user, referencia, quantidade=5, incluir_previstos=False):
    inicio_mes = inicio_do_mes(referencia)
    fim_mes = fim_do_mes(referencia)
    fluxo_mes = resumo_fluxo_periodo(user, inicio_mes, fim_mes)
    semanas_mes = _semanas_do_mes(referencia)
    semanas = []

    # As semanas exibidas podem transbordar para os meses vizinhos; a grade
    # busca também as ocorrências desses dias para que cada semana mostre o
    # fluxo real completo. A cota e os agregados mensais seguem usando apenas
    # o mês de referência (fluxo_mes).
    inicio_grade = semanas_mes[0][0]
    fim_grade = semanas_mes[-1][1]
    receitas_grade = fluxo_mes["receitas"]
    despesas_grade = fluxo_mes["despesas"]
    if inicio_grade < inicio_mes or fim_grade > fim_mes:
        receitas_grade = receitas_no_periodo(user, inicio_do_mes(inicio_grade), fim_do_mes(fim_grade))
        despesas_grade = despesas_no_periodo(user, inicio_do_mes(inicio_grade), fim_do_mes(fim_grade))

    for indice, (inicio, fim) in enumerate(semanas_mes):
        receitas_semana = [item for item in receitas_grade if inicio <= _data_fluxo_receita(item) <= fim]
        despesas_semana = [item for item in despesas_grade if inicio <= item["data"] <= fim]
        variaveis_anteriores = _somar_ocorrencias(
            fluxo_mes["despesas"],
            filtro=lambda item: item["despesa"].tipo == "variavel"
            and item["data"] < inicio
            and (incluir_previstos or item["status"] == "paga"),
        )
        # Cota orçamentária: renda planejada do mês inteiro menos compromissos
        # do mês inteiro — horizontes iguais, cota estável a semana toda.
        # incluir_previstos controla apenas se variáveis pendentes contam como gasto.
        receitas_base = fluxo_mes["receitas_total"]
        semanas_restantes = len(semanas_mes) - indice
        base_livre_confirmada = arredondar(
            receitas_base - fluxo_mes["fixos"] - fluxo_mes["parcelas"] - variaveis_anteriores
        )
        cota_semana = (
            arredondar(base_livre_confirmada / Decimal(semanas_restantes))
            if semanas_restantes > 0
            else base_livre_confirmada
        )
        gastos_semana = _somar_ocorrencias(
            despesas_semana,
            filtro=lambda item: item["despesa"].tipo == "variavel" and (incluir_previstos or item["status"] == "paga"),
        )
        gastos_pagos = _somar_ocorrencias(
            despesas_semana,
            filtro=lambda item: item["despesa"].tipo == "variavel" and item["status"] == "paga",
        )
        gastos_previstos = _somar_ocorrencias(
            despesas_semana,
            filtro=lambda item: item["despesa"].tipo == "variavel" and item["status"] == "pendente",
        )
        fixos_semana = _somar_ocorrencias(despesas_semana, filtro=lambda item: item["despesa"].tipo == "fixa")
        parcelas_semana = _somar_ocorrencias(despesas_semana, filtro=lambda item: item["despesa"].tipo == "parcelada")
        semanas.append(
            {
                "inicio": inicio,
                "fim": fim,
                "rotulo": f"{inicio:%d/%m} a {fim:%d/%m}",
                "semana_atual": inicio <= referencia <= fim,
                "receitas": _somar_ocorrencias(receitas_semana),
                "receitas_previstas": _somar_ocorrencias(receitas_semana, filtro=lambda item: item["status"] == "prevista"),
                "receitas_recebidas": _somar_ocorrencias(receitas_semana, filtro=lambda item: item["status"] == "recebida"),
                "gasto_semana": gastos_semana,
                "gastos_pagos": gastos_pagos,
                "gastos_previstos": gastos_previstos,
                "fixos": fixos_semana,
                "parcelas": parcelas_semana,
                "compromissos": arredondar(fixos_semana + parcelas_semana),
                "gasto_total": arredondar(gastos_semana + fixos_semana + parcelas_semana),
                "cota_semana": cota_semana,
                "livre_semana": arredondar(cota_semana - gastos_semana),
                "disponivel": arredondar(cota_semana - gastos_semana),
            }
        )

    if quantidade == 1:
        semanas = [semana for semana in semanas if semana["semana_atual"]] or ([semanas[0]] if semanas else [])

    semana_atual = next((semana for semana in semanas if semana["semana_atual"]), semanas[0] if semanas else None)
    return {
        "saldo_total": _saldo_total_confirmado(user, referencia),
        "semanas": semanas,
        "semana_atual": semana_atual,
        "total_comprometido": fluxo_mes["despesas_total"],
        "disponivel_apos_compromissos": fluxo_mes["saldo_planejado"],
        "base_mes": {
            "inicio_mes": inicio_mes,
            "fim_mes": fim_mes,
            "receitas": fluxo_mes["receitas_total"],
            "receitas_recebidas": fluxo_mes["receitas_recebidas"],
            "receitas_previstas": fluxo_mes["receitas_previstas"],
            "fixos": fluxo_mes["fixos"],
            "parcelas": fluxo_mes["parcelas"],
            "gastos_variaveis": fluxo_mes["variaveis"],
            "compromissos": fluxo_mes["despesas_total"],
            "sobra_mes": fluxo_mes["saldo_planejado"],
            "incluir_previstos": incluir_previstos,
        },
    }


def resumo_mensal(user, referencia):
    inicio = inicio_do_mes(referencia)
    fim = fim_do_mes(referencia)
    fluxo = resumo_fluxo_periodo(user, inicio, fim)
    planejamento = calcular_planejamento_semanal(user, referencia, quantidade=1)
    return {
        "inicio": inicio,
        "fim": fim,
        "rotulo": f"{inicio:%m/%Y}",
        "receitas": fluxo["receitas_total"],
        "receitas_previstas": fluxo["receitas_previstas"],
        "receitas_recebidas": fluxo["receitas_recebidas"],
        "gastos_pagos": fluxo["variaveis_pagas"],
        "gastos_pendentes": fluxo["variaveis_pendentes"],
        "despesas_pagas": fluxo["despesas_pagas"],
        "despesas_pendentes": fluxo["despesas_pendentes"],
        "fixos": fluxo["fixos"],
        "parcelas": fluxo["parcelas"],
        "compromissos": fluxo["despesas_total"],
        "gasto_total": fluxo["despesas_total"],
        "cota_semanal": planejamento["semana_atual"]["cota_semana"] if planejamento["semana_atual"] else Decimal("0.00"),
        "disponivel": fluxo["saldo_planejado"],
    }


def _despesas_por_data_no_periodo(user, inicio, fim):
    return _filtrar_por_data(despesas_no_periodo(user, inicio_do_mes(inicio), fim_do_mes(fim)), inicio, fim)


def _dados_graficos_periodo(user, inicio, fim, evolucao, *, usar_data=False):
    despesas_periodo = _despesas_por_data_no_periodo(user, inicio, fim) if usar_data else despesas_no_periodo(user, inicio, fim)
    por_tipo = {"Variáveis": Decimal("0.00"), "Fixas": Decimal("0.00"), "Parceladas": Decimal("0.00")}
    por_categoria = {}

    for item in despesas_periodo:
        despesa = item["despesa"]
        valor = item["valor"]
        if despesa.tipo == "fixa":
            por_tipo["Fixas"] += valor
        elif despesa.tipo == "parcelada":
            por_tipo["Parceladas"] += valor
        else:
            por_tipo["Variáveis"] += valor
        categoria = despesa.categoria or "Sem categoria"
        por_categoria[categoria] = por_categoria.get(categoria, Decimal("0.00")) + valor

    total_tipo = sum(por_tipo.values(), Decimal("0.00"))
    total_categoria = sum(por_categoria.values(), Decimal("0.00"))
    maior_categoria = max(por_categoria.values(), default=Decimal("1.00")) or Decimal("1.00")
    maior_evolucao = Decimal("1.00")
    evolucao_itens = []

    for item_evolucao in evolucao:
        ocorrencias = (
            _despesas_por_data_no_periodo(user, item_evolucao["inicio"], item_evolucao["fim"])
            if usar_data
            else despesas_no_periodo(user, item_evolucao["inicio"], item_evolucao["fim"])
        )
        gasto = _somar_ocorrencias(ocorrencias)
        evolucao_itens.append({**item_evolucao, "valor": gasto})
        maior_evolucao = max(maior_evolucao, gasto)

    tipo_percentuais = []
    cursor = Decimal("0.00")
    cores_tipo = {"Variáveis": "#1b7a4b", "Fixas": "#33518f", "Parceladas": "#b86b2e"}
    for chave, valor in por_tipo.items():
        percentual = Decimal("0.00") if not total_tipo else (valor / total_tipo) * Decimal("100")
        inicio_percentual = cursor
        cursor += percentual
        tipo_percentuais.append(
            {
                "label": chave,
                "valor": arredondar(valor),
                "percentual": int(percentual),
                "inicio": int(inicio_percentual),
                "fim": int(cursor),
                "cor": cores_tipo[chave],
            }
        )

    categoria_itens = []
    cursor_categoria = Decimal("0.00")
    for indice, (chave, valor) in enumerate(sorted(por_categoria.items(), key=lambda item: item[1], reverse=True)[:6]):
        percentual = Decimal("0.00") if not total_categoria else (valor / total_categoria) * Decimal("100")
        inicio_percentual = cursor_categoria
        cursor_categoria += percentual
        categoria_itens.append(
            {
                "label": chave,
                "valor": arredondar(valor),
                "percentual": int((valor / maior_categoria) * Decimal("100")),
                "participacao": int(percentual),
                "inicio": int(inicio_percentual),
                "fim": int(cursor_categoria),
                "cor": ["#1b7a4b", "#33518f", "#b86b2e", "#12382b", "#7c5077", "#667c66"][indice],
            }
        )

    return {
        "por_tipo": tipo_percentuais,
        "por_categoria": categoria_itens,
        "evolucao": [
            {**item, "percentual": int((item["valor"] / maior_evolucao) * Decimal("100")) if maior_evolucao else 0}
            for item in evolucao_itens
        ],
        "total": arredondar(total_tipo),
    }


def dados_graficos_dashboard(user, referencia):
    inicio = inicio_da_semana(referencia)
    primeira_semana = inicio - timedelta(days=28)
    evolucao = [
        {
            "inicio": primeira_semana + timedelta(days=indice * 7),
            "fim": primeira_semana + timedelta(days=(indice * 7) + 6),
            "rotulo": f"{primeira_semana + timedelta(days=indice * 7):%d/%m}",
            "semana_atual": primeira_semana + timedelta(days=indice * 7) == inicio,
        }
        for indice in range(5)
    ]
    return _dados_graficos_periodo(user, inicio, inicio + timedelta(days=6), evolucao, usar_data=True)


def dados_graficos_mensal(user, referencia):
    inicio = inicio_do_mes(referencia)
    primeiro_mes = adicionar_meses_data(inicio, -4)
    evolucao = []
    for indice in range(5):
        inicio_item = adicionar_meses_data(primeiro_mes, indice)
        evolucao.append(
            {
                "inicio": inicio_item,
                "fim": fim_do_mes(inicio_item),
                "rotulo": f"{inicio_item:%m/%y}",
                "semana_atual": inicio_item == inicio,
            }
        )
    return _dados_graficos_periodo(user, inicio, fim_do_mes(referencia), evolucao)
