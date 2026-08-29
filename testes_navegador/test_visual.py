"""Comparação de pixels contra a referência versionada.

Roda de propósito (`pytest -m visual`), não no `pytest` pelado — precisa do
Chromium instalado. Na primeira execução, cada tela grava sua própria
referência em testes_navegador/referencia/ e o teste correspondente é pulado;
rode de novo para comparar de verdade.
"""

import pytest

pytestmark = pytest.mark.visual


def test_tela_de_login(pagina, live_server, comparar_tela):
    pagina.goto(f"{live_server.url}/login/")
    pagina.wait_for_selector("button.auth-submit")
    comparar_tela(pagina, "login")


def test_tela_do_painel(autenticado, comparar_tela):
    comparar_tela(autenticado, "painel")


def test_tela_de_despesas(autenticado, live_server, comparar_tela):
    autenticado.goto(f"{live_server.url}/financeiro/despesas/")
    autenticado.wait_for_selector("h2:has-text('Despesas')")
    comparar_tela(autenticado, "despesas")


def test_tela_de_controle(autenticado, live_server, comparar_tela):
    autenticado.goto(f"{live_server.url}/financeiro/controle/")
    autenticado.wait_for_selector("h2:has-text('Controle')")
    comparar_tela(autenticado, "controle")


def test_painel_no_celular(pagina, live_server, usuario_demo, comparar_tela):
    from testes_navegador.conftest import SENHA, USUARIO

    pagina.set_viewport_size({"width": 390, "height": 844})
    pagina.goto(f"{live_server.url}/login/")
    pagina.fill("#id_username", USUARIO)
    pagina.fill("#id_password", SENHA)
    pagina.click("button.auth-submit")
    pagina.wait_for_selector("text=Últimos lançamentos")
    comparar_tela(pagina, "painel-celular")
