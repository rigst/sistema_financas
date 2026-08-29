"""Os caminhos inteiros, do jeito que uma pessoa percorre.

O que estes testes pegam e os de unidade não: template que não renderiza,
classe que não existe mais no CSS vendorado, botão coberto por outro
elemento, JavaScript que quebra ao trocar o casco por sidebar. São lentos,
então cobrem os caminhos que doem se quebrarem, não todos.
"""

import re

import pytest

from testes_navegador.conftest import SENHA, USUARIO

pytestmark = pytest.mark.e2e


def test_entrar_e_ver_o_painel(pagina, live_server, usuario_demo):
    pagina.goto(f"{live_server.url}/login/")
    pagina.fill("#id_username", USUARIO)
    pagina.fill("#id_password", SENHA)
    pagina.click("button.auth-submit")

    pagina.wait_for_selector("text=Últimos lançamentos")
    assert "Aluguel" in pagina.content()
    assert "Salário" in pagina.content()


def test_senha_errada_nao_entra(pagina, live_server, usuario_demo):
    pagina.goto(f"{live_server.url}/login/")
    pagina.fill("#id_username", USUARIO)
    pagina.fill("#id_password", "isso-nao-e-a-senha")
    pagina.click("button.auth-submit")

    pagina.wait_for_selector("#id_password")
    assert "/login/" in pagina.url


def test_visitante_ganha_conta_temporaria(pagina, live_server, documentos_legais_publicados):
    """Botão de visitante leva ao portão de aceite, não direto para dentro —
    o texto que a pessoa precisa ler não cabe ao lado de um botão."""
    pagina.goto(f"{live_server.url}/login/")
    pagina.click("text=Entrar como visitante")
    pagina.wait_for_url(re.compile(r"/legal/aceite/"))
    assert pagina.locator("button:has-text('Aceitar e entrar')").is_visible()


def test_navegacao_lateral_leva_as_telas_certas(autenticado, live_server):
    autenticado.click(".ds-nav-link:has-text('Despesas')")
    autenticado.wait_for_selector("h2:has-text('Despesas')")
    assert "Supermercado" in autenticado.content()

    autenticado.click(".ds-nav-link:has-text('Receitas')")
    autenticado.wait_for_selector("h2:has-text('Receitas')")
    assert "Freelance" in autenticado.content()

    autenticado.click(".ds-nav-link:has-text('Controle')")
    autenticado.wait_for_selector("h2:has-text('Controle')")
    assert "Viagem" in autenticado.content()
    assert "Emergência" in autenticado.content()


def test_criar_despesa_variavel(autenticado, live_server):
    autenticado.goto(f"{live_server.url}/financeiro/despesas/nova/")
    autenticado.fill("#id_descricao", "Farmácia")
    autenticado.fill("#id_valor", "89,90")
    autenticado.click("button:has-text('Salvar despesa')")

    autenticado.wait_for_selector("h2:has-text('Despesas')")
    assert "Farmácia" in autenticado.content()
    assert "R$ 89,90" in autenticado.content()


def test_marcar_despesa_como_paga_mostra_o_selo(autenticado, live_server):
    autenticado.goto(f"{live_server.url}/financeiro/despesas/")
    linha = autenticado.locator("tr", has_text="Supermercado")
    assert "status-pendente" in linha.locator(".badge").get_attribute("class")

    linha.locator("button[title='Marcar como paga']").click()
    autenticado.wait_for_selector("tr:has-text('Supermercado') .badge.status-paga")


def test_criar_meta_e_ver_no_painel(autenticado, live_server):
    autenticado.goto(f"{live_server.url}/financeiro/controle/reservas/nova/")
    autenticado.fill("#id_nome", "Casa nova")
    autenticado.fill("#id_valor_alvo", "50000,00")
    autenticado.click("button:has-text('Salvar reserva')")

    autenticado.wait_for_selector("h2:has-text('Controle')")
    assert "Casa nova" in autenticado.content()

    autenticado.goto(f"{live_server.url}/")
    autenticado.wait_for_selector("text=Metas")
    assert "Casa nova" in autenticado.content()


def test_sair_volta_para_o_login(autenticado, live_server):
    autenticado.click("button:has-text('Sair')")
    autenticado.wait_for_url(re.compile(r"/login/"))
    assert autenticado.locator("#id_username").is_visible()


def test_gaveta_da_lateral_abre_no_celular(pagina, live_server, usuario_demo):
    pagina.set_viewport_size({"width": 390, "height": 844})
    pagina.goto(f"{live_server.url}/login/")
    pagina.fill("#id_username", USUARIO)
    pagina.fill("#id_password", SENHA)
    pagina.click("button.auth-submit")
    pagina.wait_for_selector("text=Últimos lançamentos")

    # Fechada: o link de navegação não deve estar clicável no celular.
    assert not pagina.locator(".ds-nav-link:has-text('Despesas')").is_visible()

    pagina.click(".ds-burger")
    pagina.click(".ds-nav-link:has-text('Despesas')")
    pagina.wait_for_selector("h2:has-text('Despesas')")


def test_manual_carrega(autenticado, live_server):
    autenticado.goto(f"{live_server.url}/manual/")
    autenticado.wait_for_selector("h2:has-text('Manual')")


def test_termos_publicados_carregam(autenticado, live_server, documentos_legais_publicados):
    autenticado.goto(f"{live_server.url}/termos/")
    autenticado.wait_for_selector("h1:has-text('Termos de Uso')")
