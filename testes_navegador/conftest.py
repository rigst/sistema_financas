"""Infra dos testes de navegador (e2e e visual).

Diferente do que um app com SSE precisaria, o financas é WSGI puro — o
`live_server` do pytest-django (que já sobe `runserver` numa thread e serve os
estáticos automaticamente, por causa do `django.contrib.staticfiles`) é
suficiente, sem precisar subir um processo à parte.

Um banco de teste fresco não tem nenhum `DocumentoLegal` publicado, então o
portão de aceite (`legal.middleware.AceiteObrigatorioMiddleware`) fica
naturalmente inerte — não precisa ser contornado aqui.
"""

import datetime
import os
from unittest.mock import patch

import pytest

# pytest-playwright mantém um loop asyncio vivo na mesma thread; sem isto o
# Django recusa o acesso síncrono ao banco do `live_server` achando que está
# num contexto assíncrono. Só afeta este processo de teste.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

USUARIO = "demo"
SENHA = "cofre-navegador-1234"

# O painel mostra "esta semana" e "este mês": sem um relógio fixo, o texto do
# cabeçalho e os totais mudam sozinhos quando o teste roda num dia diferente
# do que gravou a referência visual — foi assim que a data virou entre duas
# capturas desta mesma suíte e o "mudou 15% dos pixels" não tinha nada a ver
# com CSS. Meio do mês, de propósito: sobra folga para os "-10 dias" da
# parcela sem cruzar mês.
DATA_FIXA = datetime.date(2026, 8, 15)


@pytest.fixture
def tempo_fixo():
    """Trava `timezone.localdate()`/`timezone.now()` em DATA_FIXA.

    Só assim o painel (que calcula "semana atual" e "mês atual" a partir do
    relógio de verdade) fica determinístico entre execuções. O patch mira o
    atributo no módulo `django.utils.timezone`, não um nome importado — é
    onde `from django.utils import timezone; timezone.localdate()` de fato
    busca a função a cada chamada, inclusive nas requisições que o
    `live_server` atende numa thread à parte.
    """
    agora_fixo = datetime.datetime.combine(
        DATA_FIXA, datetime.time(12, 0), tzinfo=datetime.timezone.utc
    )
    with patch("django.utils.timezone.localdate", return_value=DATA_FIXA), \
         patch("django.utils.timezone.now", return_value=agora_fixo):
        yield DATA_FIXA


@pytest.fixture
def pagina(page):
    """Uma aba de navegador com viewport e movimento fixos.

    Movimento desligado por duas razões: a animação de entrada do `.ds-page`
    tornaria cada captura uma corrida contra o relógio, e respeitar
    `prefers-reduced-motion` é uma das coisas que se quer garantir que
    continua funcionando.
    """
    page.set_default_timeout(15000)
    page.emulate_media(reduced_motion="reduce")
    page.set_viewport_size({"width": 1440, "height": 900})
    return page


@pytest.fixture
def usuario_demo(live_server, tempo_fixo, django_user_model):
    """Usuário com um mês de lançamentos típicos — despesa fixa paga, despesa
    variável pendente, despesa parcelada, receita fixa recebida, receita
    variável prevista e duas metas — o bastante para painel, listas e
    controle terem o que mostrar.

    As datas partem de `tempo_fixo` (não de "hoje" de verdade): é o que faz
    os totais do painel — que somam por semana e mês corrente — saírem iguais
    não importa em que dia real a suíte rodar.
    """
    from datetime import timedelta
    from decimal import Decimal

    from financeiro.models import (
        Despesa,
        PagamentoDespesa,
        Receita,
        RecebimentoReceita,
        Reserva,
    )

    user = django_user_model.objects.create_user(username=USUARIO, password=SENHA)
    hoje = tempo_fixo
    competencia = hoje.replace(day=1)

    salario = Receita.objects.create(
        descricao="Salário", tipo="fixa", valor=Decimal("8400.00"), status="prevista",
        data=hoje, competencia=competencia, categoria="Trabalho", criado_por=user,
    )
    Receita.objects.create(
        descricao="Freelance", tipo="variavel", valor=Decimal("1200.00"),
        data=hoje - timedelta(days=3), competencia=competencia, status="prevista",
        categoria="Extra", criado_por=user,
    )
    aluguel = Despesa.objects.create(
        descricao="Aluguel", tipo="fixa", valor=Decimal("2100.00"),
        data=hoje, competencia=competencia, categoria="Moradia", criado_por=user,
    )
    Despesa.objects.create(
        descricao="Supermercado", tipo="variavel", valor=Decimal("340.50"),
        data=hoje - timedelta(days=1), competencia=competencia, status="pendente",
        categoria="Alimentação", criado_por=user,
    )
    Despesa.objects.create(
        descricao="Notebook", tipo="parcelada", valor=Decimal("3600.00"),
        parcelas=12, parcela_atual=3, data=hoje - timedelta(days=10),
        competencia=competencia, categoria="Tecnologia", criado_por=user,
    )
    Reserva.objects.create(
        nome="Viagem", valor_atual=Decimal("2400.00"), valor_alvo=Decimal("6000.00"),
        criado_por=user,
    )
    Reserva.objects.create(
        nome="Emergência", valor_atual=Decimal("5000.00"), valor_alvo=Decimal("10000.00"),
        criado_por=user,
    )
    PagamentoDespesa.objects.create(despesa=aluguel, competencia=competencia)
    RecebimentoReceita.objects.create(receita=salario, competencia=competencia)

    return user


@pytest.fixture
def documentos_legais_publicados(live_server):
    """Termos e Privacidade publicados — o portão de visitante e o de
    re-aceite só têm o que mostrar quando existe uma versão vigente."""
    from legal.models import DocumentoLegal

    for tipo, titulo in (("termos", "Termos de Uso"), ("privacidade", "Política de Privacidade")):
        doc = DocumentoLegal.objects.create(
            tipo=tipo, versao="1.0", titulo=titulo,
            corpo_md=f"# {titulo}\n\nTexto de teste.",
        )
        doc.publicar()


@pytest.fixture
def autenticado(pagina, live_server, usuario_demo):
    pagina.goto(f"{live_server.url}/login/")
    pagina.fill("#id_username", USUARIO)
    pagina.fill("#id_password", SENHA)
    pagina.click("button.auth-submit")
    # Esperar pelo conteúdo do painel, não pela URL: um glob de URL casa com a
    # própria tela de login e o teste seguiria como se tivesse entrado.
    pagina.wait_for_selector("text=Últimos lançamentos")
    return pagina


# ---------------------------------------------------------------------------
# Comparação de telas
# ---------------------------------------------------------------------------
# CSS em cascata quebra em silêncio: o servidor responde 200, o HTML está
# certo e a tela está destruída. Nenhum teste de Python percebe isso —
# comparar pixels é a única rede que pega.

from pathlib import Path  # noqa: E402

REFERENCIA = Path(__file__).parent / "referencia"
DIFERENCAS = Path(__file__).parent / "diferencas"

# Antialiasing de fonte varia entre execuções mesmo sem mudança nenhuma. A
# folga é pequena de propósito: qualquer alteração real de layout mexe em
# muito mais que isto.
TOLERANCIA = 0.0015


def pytest_addoption(parser):
    parser.addoption(
        "--atualizar-telas",
        action="store_true",
        help="Regrava as capturas de referência em vez de comparar com elas.",
    )


@pytest.fixture
def comparar_tela(request):
    """Captura a tela e confronta com a referência versionada.

    Falhar aqui não significa "está errado": significa "mudou". Olhe a imagem
    de diferença gravada em testes_navegador/diferencas/ e, se a mudança era
    o que você queria, regrave a referência com --atualizar-telas.
    """
    from PIL import Image
    from pixelmatch.contrib.PIL import pixelmatch

    atualizar = request.config.getoption("--atualizar-telas")
    REFERENCIA.mkdir(exist_ok=True)

    def comparar(pagina, nome, mascarar=()):
        # Nada de `animations="disabled"`: em capturas de página inteira com
        # a lateral em `position: fixed`, essa opção do Playwright descola o
        # `.ds-frame` do lugar por um frame (bug de composição do Chromium,
        # não do CSS do app — reproduzido também fora da suíte). O
        # `prefers-reduced-motion` que `pagina` já emula é o que de fato
        # precisa funcionar, e é ele quem congela a animação de entrada aqui.
        #
        # `networkidle` garante que a fonte já chegou, não que ela já foi
        # trocada na tela: o "swap" de FOIT para o glifo de verdade ainda gera
        # um reflow depois disso, e pegar esse instante no meio produz o mesmo
        # tipo de tela deslocada. Esperar `document.fonts.ready` e mais um
        # quadro é o que faltava.
        pagina.evaluate("document.fonts.ready.then(() => new Promise(requestAnimationFrame))")
        pagina.wait_for_timeout(120)
        bytes_tela = pagina.screenshot(
            full_page=True,
            caret="hide",
            mask=[pagina.locator(s) for s in mascarar],
        )

        alvo = REFERENCIA / f"{nome}.png"
        if atualizar or not alvo.exists():
            alvo.write_bytes(bytes_tela)
            if not atualizar:
                pytest.skip(f"Referência de '{nome}' criada agora; rode de novo para comparar.")
            return

        import io

        atual = Image.open(io.BytesIO(bytes_tela)).convert("RGB")
        referencia = Image.open(alvo).convert("RGB")

        if atual.size != referencia.size:
            _gravar_falha(nome, atual, None)
            pytest.fail(
                f"'{nome}' mudou de tamanho: {referencia.size} virou {atual.size}. "
                f"A captura nova está em testes_navegador/diferencas/."
            )

        diferenca = Image.new("RGBA", atual.size)
        pixels = pixelmatch(atual, referencia, diferenca, includeAA=True, threshold=0.12)
        proporcao = pixels / (atual.size[0] * atual.size[1])

        if proporcao > TOLERANCIA:
            _gravar_falha(nome, atual, diferenca)
            pytest.fail(
                f"'{nome}' mudou em {pixels} pixels ({proporcao:.2%}). "
                f"Veja testes_navegador/diferencas/{nome}-diferenca.png. "
                f"Se a mudança era intencional, rode com --atualizar-telas."
            )

    return comparar


def _gravar_falha(nome, atual, diferenca):
    DIFERENCAS.mkdir(exist_ok=True)
    atual.save(DIFERENCAS / f"{nome}-atual.png")
    if diferenca is not None:
        diferenca.save(DIFERENCAS / f"{nome}-diferenca.png")
