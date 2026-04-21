from datetime import timedelta
from decimal import Decimal

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from .models import Despesa, Receita, adicionar_meses_data, arredondar

SOMA_DECIMAL = DecimalField(max_digits=14, decimal_places=2)


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


def _somar(queryset, campo="valor"):
    return arredondar(queryset.aggregate(total=Coalesce(Sum(campo), Value(0), output_field=SOMA_DECIMAL))["total"])


def _despesas_no_periodo(user, inicio, fim):
    despesas = Despesa.objects.filter(criado_por=user).exclude(status="cancelada")
    ocorrencias = []
    for despesa in despesas:
        for ocorrencia in despesa.ocorrencias(inicio, fim):
            ocorrencias.append({"despesa": despesa, **ocorrencia})
    return ocorrencias


def _semanas_do_mes(referencia):
    inicio_mes = inicio_do_mes(referencia)
    fim_mes = fim_do_mes(referencia)
    inicio = inicio_da_semana(inicio_mes)
    semanas = []
    while inicio <= fim_mes:
        fim = inicio + timedelta(days=6)
        semanas.append((inicio, fim))
        inicio += timedelta(days=7)
    return semanas


def _base_mensal_para_semanas(user, referencia):
    receitas = Receita.objects.filter(criado_por=user)
    inicio_mes = inicio_do_mes(referencia)
    fim_mes = fim_do_mes(referencia)
    receitas_mes = receitas.filter(data__range=(inicio_mes, fim_mes))
    ocorrencias_mes = _despesas_no_periodo(user, inicio_mes, fim_mes)
    receitas_total = _somar(receitas_mes)
    entradas_recebidas = _somar(receitas_mes.filter(status="recebida"))
    entradas_previstas = _somar(receitas_mes.filter(status="prevista"))
    fixos_mes = arredondar(sum((item["valor"] for item in ocorrencias_mes if item["despesa"].tipo == "fixa"), Decimal("0.00")))
    parcelas_mes = arredondar(sum((item["valor"] for item in ocorrencias_mes if item["despesa"].tipo == "parcelada"), Decimal("0.00")))
    variaveis_pagas_mes = arredondar(
        sum((item["valor"] for item in ocorrencias_mes if item["despesa"].tipo == "variavel" and item["despesa"].status == "paga"), Decimal("0.00"))
    )
    variaveis_pendentes_mes = arredondar(
        sum((item["valor"] for item in ocorrencias_mes if item["despesa"].tipo == "variavel" and item["despesa"].status == "pendente"), Decimal("0.00"))
    )
    compromissos_mes = arredondar(fixos_mes + parcelas_mes)
    sobra_mes = arredondar(receitas_total - compromissos_mes - variaveis_pagas_mes)
    cota_semanal = arredondar(sobra_mes / Decimal("4.00"))
    return {
        "inicio_mes": inicio_mes,
        "fim_mes": fim_mes,
        "receitas": receitas_total,
        "receitas_recebidas": entradas_recebidas,
        "receitas_previstas": entradas_previstas,
        "fixos": fixos_mes,
        "parcelas": parcelas_mes,
        "compromissos": compromissos_mes,
        "gastos_variaveis_pagos": variaveis_pagas_mes,
        "gastos_variaveis_pendentes": variaveis_pendentes_mes,
        "sobra_mes": sobra_mes,
        "cota_semanal": cota_semanal,
    }


def calcular_planejamento_semanal(user, referencia, quantidade=5):
    receitas = Receita.objects.filter(criado_por=user)
    despesas = Despesa.objects.filter(criado_por=user).exclude(status="cancelada")
    saldo_total = arredondar(_somar(receitas.filter(status="recebida")) - _somar(despesas.filter(status="paga")))
    base_mes = _base_mensal_para_semanas(user, referencia)
    if quantidade == 1:
        periodos = [(inicio_da_semana(referencia), fim_da_semana(referencia))]
    else:
        periodos = _semanas_do_mes(referencia)
    semanas = []

    for inicio, fim in periodos:
        receitas_semana = receitas.filter(data__range=(inicio, fim))
        entradas_previstas = _somar(receitas_semana.filter(status="prevista"))
        entradas_recebidas = _somar(receitas_semana.filter(status="recebida"))
        ocorrencias = _despesas_no_periodo(user, inicio, fim)
        gastos_pagos = arredondar(
            sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "variavel" and item["despesa"].status == "paga"), Decimal("0.00"))
        )
        fixos = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "fixa"), Decimal("0.00")))
        parcelas = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "parcelada"), Decimal("0.00")))
        variaveis_pendentes = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "variavel" and item["despesa"].status == "pendente"), Decimal("0.00")))
        compromissos = arredondar(fixos + parcelas + variaveis_pendentes)
        livre_semana = arredondar(base_mes["cota_semanal"] - gastos_pagos)
        semanas.append(
            {
                "inicio": inicio,
                "fim": fim,
                "rotulo": f"{inicio:%d/%m} a {fim:%d/%m}",
                "semana_atual": inicio <= referencia <= fim,
                "receitas": arredondar(entradas_previstas + entradas_recebidas),
                "receitas_previstas": entradas_previstas,
                "receitas_recebidas": entradas_recebidas,
                "gastos_pagos": gastos_pagos,
                "gastos_pendentes": variaveis_pendentes,
                "fixos": fixos,
                "parcelas": parcelas,
                "compromissos": compromissos,
                "gasto_total": arredondar(gastos_pagos + compromissos),
                "cota_semana": base_mes["cota_semanal"],
                "gasto_semana": gastos_pagos,
                "livre_semana": livre_semana,
                "disponivel": livre_semana,
            }
        )

    semana_atual = next((semana for semana in semanas if semana["semana_atual"]), semanas[0] if semanas else None)
    total_comprometido = arredondar(base_mes["compromissos"] + base_mes["gastos_variaveis_pagos"])
    disponivel_apos_compromissos = base_mes["sobra_mes"]
    return {
        "saldo_total": saldo_total,
        "semanas": semanas,
        "semana_atual": semana_atual,
        "total_comprometido": total_comprometido,
        "disponivel_apos_compromissos": disponivel_apos_compromissos,
        "base_mes": base_mes,
    }


def resumo_mensal(user, referencia):
    receitas = Receita.objects.filter(criado_por=user)
    inicio = inicio_do_mes(referencia)
    fim = fim_do_mes(referencia)
    receitas_mes = receitas.filter(data__range=(inicio, fim))
    base_mes = _base_mensal_para_semanas(user, referencia)
    entradas_previstas = _somar(receitas_mes.filter(status="prevista"))
    entradas_recebidas = _somar(receitas_mes.filter(status="recebida"))
    ocorrencias = _despesas_no_periodo(user, inicio, fim)
    gastos_pagos = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "variavel" and item["despesa"].status == "paga"), Decimal("0.00")))
    fixos = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "fixa"), Decimal("0.00")))
    parcelas = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "parcelada"), Decimal("0.00")))
    variaveis_pendentes = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "variavel" and item["despesa"].status == "pendente"), Decimal("0.00")))
    compromissos = arredondar(fixos + parcelas + variaveis_pendentes)
    return {
        "inicio": inicio,
        "fim": fim,
        "rotulo": f"{inicio:%m/%Y}",
        "receitas": arredondar(entradas_previstas + entradas_recebidas),
        "receitas_previstas": entradas_previstas,
        "receitas_recebidas": entradas_recebidas,
        "gastos_pagos": gastos_pagos,
        "gastos_pendentes": variaveis_pendentes,
        "fixos": fixos,
        "parcelas": parcelas,
        "compromissos": compromissos,
        "gasto_total": arredondar(gastos_pagos + compromissos),
        "cota_semanal": base_mes["cota_semanal"],
        "disponivel": base_mes["sobra_mes"],
    }


def _dados_graficos_periodo(user, inicio, fim, evolucao):
    despesas_periodo = _despesas_no_periodo(user, inicio, fim)
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
    maior_categoria = max(por_categoria.values(), default=Decimal("0.00")) or Decimal("1.00")
    maior_evolucao = Decimal("1.00")
    evolucao_itens = []
    for item_evolucao in evolucao:
        inicio_item = item_evolucao["inicio"]
        fim_item = item_evolucao["fim"]
        ocorrencias = _despesas_no_periodo(user, inicio_item, fim_item)
        gasto = arredondar(sum((item["valor"] for item in ocorrencias), Decimal("0.00")))
        evolucao_itens.append({**item_evolucao, "valor": gasto})
        maior_evolucao = max(maior_evolucao, gasto)

    tipo_percentuais = []
    cursor = Decimal("0.00")
    cores_tipo = {
        "Variáveis": "#2f7d69",
        "Fixas": "#8b6f47",
        "Parceladas": "#c65f46",
    }
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
                "cor": ["#2f7d69", "#8b6f47", "#c65f46", "#58726b", "#9a8b66", "#7f5d58"][indice],
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
    return _dados_graficos_periodo(user, inicio, inicio + timedelta(days=6), evolucao)


def dados_graficos_mensal(user, referencia):
    inicio = inicio_do_mes(referencia)
    primeiro_mes = adicionar_meses_data(inicio, -4)
    evolucao = []
    for indice in range(5):
        inicio_item = adicionar_meses_data(primeiro_mes, indice)
        fim_item = fim_do_mes(inicio_item)
        evolucao.append(
            {
                "inicio": inicio_item,
                "fim": fim_item,
                "rotulo": f"{inicio_item:%m/%y}",
                "semana_atual": inicio_item == inicio,
            }
        )
    return _dados_graficos_periodo(user, inicio, fim_do_mes(referencia), evolucao)
