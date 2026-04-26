import json
from datetime import timedelta
from decimal import Decimal
from urllib import error, request

from django.conf import settings
from django.utils import timezone

from financeiro.models import MentoriaFinanceiraIA, Reserva, arredondar
from financeiro.planejamento import resumo_fluxo_periodo


def _decimal_para_json(valor):
    return float(arredondar(valor))


def _somar(valores):
    return arredondar(sum(valores, Decimal("0.00")))


def _mapear_valores(itens, chave_func):
    totais = {}
    for item in itens:
        chave = chave_func(item)
        totais[chave] = totais.get(chave, Decimal("0.00")) + item["valor"]
    return {chave: _decimal_para_json(valor) for chave, valor in sorted(totais.items())}


def coletar_dados_mentoria(user, referencia=None):
    fim = referencia or timezone.localdate()
    inicio = fim - timedelta(days=30)
    fluxo = resumo_fluxo_periodo(user, inicio, fim)
    receitas = fluxo["receitas"]
    reservas = Reserva.objects.filter(criado_por=user, ativa=True)
    ocorrencias = fluxo["despesas"]

    receitas_recebidas = fluxo["receitas_recebidas"]
    receitas_previstas = fluxo["receitas_previstas"]
    despesas_total = fluxo["despesas_total"]
    gastos_total = fluxo["despesas_total"]

    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "resumo": {
            "receitas_recebidas": _decimal_para_json(receitas_recebidas),
            "receitas_previstas": _decimal_para_json(receitas_previstas),
            "despesas_total": _decimal_para_json(despesas_total),
            "gastos_total": _decimal_para_json(gastos_total),
            "resultado_recebido_menos_despesas": _decimal_para_json(receitas_recebidas - despesas_total),
        },
        "gastos_por_tipo": _mapear_valores(ocorrencias, lambda item: item["despesa"].get_tipo_display()),
        "gastos_por_categoria": _mapear_valores(ocorrencias, lambda item: item["despesa"].categoria or "Sem categoria"),
        "maiores_despesas": [
            {
                "data": item["data"].isoformat(),
                "descricao": item["despesa"].descricao,
                "tipo": item["despesa"].get_tipo_display(),
                "categoria": item["despesa"].categoria or "Sem categoria",
                "status": f"Competência {item['competencia']:%m/%Y}",
                "valor": _decimal_para_json(item["valor"]),
            }
            for item in sorted(ocorrencias, key=lambda item: item["valor"], reverse=True)[:12]
        ],
        "receitas": [
            {
                "data": receita["data"].isoformat(),
                "descricao": receita["descricao"],
                "categoria": receita["categoria"] or "Sem categoria",
                "status": "Recebida" if receita["status"] == "recebida" else "Prevista",
                "valor": _decimal_para_json(receita["valor"]),
            }
            for receita in sorted(
                [
                    {
                        "data": item["data"],
                        "descricao": item["receita"].descricao,
                        "categoria": item["receita"].categoria,
                        "status": item["status"],
                        "valor": item["valor"],
                    }
                    for item in receitas
                ],
                key=lambda item: (item["valor"], item["data"]),
                reverse=True,
            )[:12]
        ],
        "metas_reservas": [
            {
                "nome": reserva.nome,
                "valor_atual": _decimal_para_json(reserva.valor_atual),
                "valor_alvo": _decimal_para_json(reserva.valor_alvo),
                "percentual": _decimal_para_json(reserva.percentual_concluido),
            }
            for reserva in reservas.order_by("nome")
        ],
    }


def _extrair_texto_openai(resposta):
    if resposta.get("output_text"):
        return str(resposta["output_text"]).strip()

    partes = []
    for item in resposta.get("output", []):
        if item.get("type") != "message":
            continue
        for conteudo in item.get("content", []):
            if conteudo.get("type") in {"output_text", "text"} and conteudo.get("text"):
                partes.append(str(conteudo["text"]))
    return "\n".join(partes).strip()


def _post_openai(payload):
    requisicao = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(requisicao, timeout=settings.OPENAI_TIMEOUT_SECONDS) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def _erro_modelo_inexistente(exc, detalhe):
    if exc.code != 400:
        return False
    return "model_not_found" in detalhe or "does not exist" in detalhe


def _chamar_openai_com_fallback(payload, modelo):
    try:
        return _post_openai(payload), modelo
    except error.HTTPError as exc:
        detalhe = exc.read().decode("utf-8", errors="ignore")
        fallback = getattr(settings, "OPENAI_MENTORIA_FALLBACK_MODEL", "").strip()
        if fallback and fallback != modelo and _erro_modelo_inexistente(exc, detalhe):
            payload = {**payload, "model": fallback}
            try:
                return _post_openai(payload), fallback
            except error.HTTPError as fallback_exc:
                detalhe_fallback = fallback_exc.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"Erro da OpenAI ao gerar mentoria: {fallback_exc.code} {detalhe_fallback[:300]}") from fallback_exc
        raise RuntimeError(f"Erro da OpenAI ao gerar mentoria: {exc.code} {detalhe[:300]}") from exc


def gerar_mentoria_financeira(user):
    if not settings.OPENAI_API_KEY:
        raise ValueError("Configure OPENAI_API_KEY para gerar a mentoria financeira da IA.")

    dados = coletar_dados_mentoria(user)
    modelo = settings.OPENAI_MENTORIA_MODEL or "gpt-5-mini"
    payload = {
        "model": modelo,
        "instructions": (
            "Você é uma mentora financeira objetiva para uma pessoa física. "
            "Analise apenas os dados enviados, não invente valores e não dê aconselhamento de investimento. "
            "Responda em português do Brasil, em no máximo 220 palavras. "
            "Formato obrigatório: primeiro um parágrafo curto chamado 'Análise geral' sem citar números, valores, "
            "percentuais ou datas; nele diga quais maiores gastos parecem ajustáveis e quais gastos recorrentes "
            "tendem a se repetir. Depois faça uma lista numerada com exatamente 5 metas claras e objetivas. "
            "Nas 5 metas, use valores em reais quando os dados permitirem, defina limites semanais ou mensais, "
            "e diga exatamente o que fazer para gastar menos e avançar nas metas/reservas."
        ),
        "input": "Dados financeiros dos últimos 30 dias em JSON:\n" + json.dumps(dados, ensure_ascii=False),
    }

    try:
        resposta, modelo_usado = _chamar_openai_com_fallback(payload, modelo)
    except error.URLError as exc:
        raise RuntimeError("Não foi possível conectar à OpenAI para gerar a mentoria.") from exc

    conteudo = _extrair_texto_openai(resposta)
    if not conteudo:
        raise RuntimeError("A OpenAI não retornou texto para a mentoria financeira.")

    return MentoriaFinanceiraIA.objects.create(
        criado_por=user,
        periodo_inicio=dados["periodo"]["inicio"],
        periodo_fim=dados["periodo"]["fim"],
        conteudo=conteudo,
        dados_enviados=dados,
        modelo=modelo_usado,
    )
