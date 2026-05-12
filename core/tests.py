from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.formatting import parse_decimal_br
from financeiro.models import CompartilhamentoDespesa, Despesa, MentoriaFinanceiraIA, ParticipanteCompartilhamentoDespesa, Receita


class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dashboard_user",
            password="senha-forte-123",
        )
        self.client.force_login(self.user)
        Receita.objects.create(
            descricao="Salário recente",
            valor=Decimal("1200.00"),
            data=timezone.localdate(),
            status="recebida",
            categoria="Salário",
            criado_por=self.user,
        )
        Despesa.objects.create(
            descricao="Despesa antiga",
            valor=Decimal("800.00"),
            data=timezone.localdate() - timedelta(days=45),
            status="paga",
            tipo="variavel",
            categoria="Mercado",
            criado_por=self.user,
        )
    def test_dashboard_filtra_periodo_e_exibe_indicadores(self):
        response = self.client.get(reverse("dashboard"), {"periodo": "30"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "R$ 1.200,00")
        self.assertContains(response, "Máximo semanal")
        self.assertContains(response, "Gastos por tipo")
        self.assertEqual(response.context["indicadores"]["total_transacoes"], 1)

    def test_dashboard_exibe_saldo_e_ultimos_lancamentos_financeiros(self):
        Despesa.objects.create(
            descricao="Compra cancelada",
            valor=Decimal("300.00"),
            data=timezone.localdate(),
            status="cancelada",
            tipo="variavel",
            categoria="Mercado",
            criado_por=self.user,
        )
        Despesa.objects.create(
            descricao="Compra parcelada",
            valor=Decimal("600.00"),
            data=timezone.localdate(),
            status="pendente",
            tipo="parcelada",
            categoria="Compras",
            parcelas=6,
            parcela_atual=3,
            criado_por=self.user,
        )

        response = self.client.get(reverse("dashboard"), {"periodo": "todos"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Máximo semanal")
        self.assertContains(response, "Salário recente")
        self.assertContains(response, "Compra parcelada")
        self.assertContains(response, "3/6")
        self.assertNotContains(response, "R$ 300,00")
        self.assertIn("planejamento_semanal", response.context)
        lancamentos = [item["descricao"] for item in response.context["ultimos_lancamentos"]]
        self.assertIn("Salário recente", lancamentos)
        self.assertNotIn("Compra cancelada", lancamentos)

    def test_dashboard_resume_compartilhamentos(self):
        outro = get_user_model().objects.create_user(username="dashboard_outro")
        despesa = Despesa.objects.create(
            descricao="Despesa dividida",
            valor=Decimal("40.00"),
            data=timezone.localdate(),
            status="pendente",
            tipo="variavel",
            categoria="Casa",
            criado_por=outro,
        )
        compartilhamento = CompartilhamentoDespesa.objects.create(
            despesa=despesa,
            criado_por=outro,
            valor_total=Decimal("80.00"),
            pagador=outro,
        )
        ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=self.user,
            valor=Decimal("40.00"),
            status="pendente",
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compartilhamentos")
        self.assertContains(response, "R$ 40,00")
        self.assertEqual(response.context["compartilhadas_dashboard"]["pendentes"], 1)

    def test_dashboard_limita_ultimos_lancamentos_a_cinco(self):
        hoje = timezone.localdate()
        for indice in range(6):
            Receita.objects.create(
                descricao=f"Lançamento {indice}",
                valor=Decimal("10.00"),
                data=hoje + timedelta(days=indice + 1),
                status="recebida",
                categoria="Extra",
                criado_por=self.user,
            )

        response = self.client.get(reverse("dashboard"), {"periodo": "todos"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["ultimos_lancamentos"]), 5)
        self.assertContains(response, "Lançamento 5")
        self.assertNotContains(response, "Lançamento 0")

    def test_dashboard_permite_navegar_por_semana(self):
        response = self.client.get(reverse("dashboard"), {"semana": "2026-04-20", "periodo": "todos"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "20/04/2026 a 26/04/2026")
        self.assertContains(response, "semana=2026-04-13")
        self.assertContains(response, "semana=2026-04-27")

    def test_dashboard_exibe_ultima_mentoria_ia_salva(self):
        MentoriaFinanceiraIA.objects.create(
            criado_por=self.user,
            periodo_inicio=timezone.localdate() - timedelta(days=30),
            periodo_fim=timezone.localdate(),
            conteudo="Análise salva pela IA.\n1. Reduza gastos pequenos.",
            modelo="modelo-teste",
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mentoria financeira da IA")
        self.assertContains(response, "Análise salva pela IA.")
        self.assertContains(response, 'class="ai-mentor-summary"', html=False)
        self.assertContains(response, 'class="ai-mentor-list"', html=False)
        self.assertContains(response, "Gerar análise")

    @override_settings(OPENAI_API_KEY="sk-teste", OPENAI_MENTORIA_MODEL="modelo-teste")
    @patch("core.ai_mentoria._post_openai")
    def test_botao_gera_mentoria_ia_e_salva_resultado(self, post_openai):
        post_openai.return_value = {
            "output_text": "Seu gasto do mês ficou concentrado em mercado.\n1. Defina um limite semanal."
        }

        response = self.client.post(reverse("gerar_mentoria_ia"), follow=True)

        self.assertRedirects(response, reverse("dashboard"))
        mentoria = MentoriaFinanceiraIA.objects.get(criado_por=self.user)
        self.assertIn("Seu gasto do mês", mentoria.conteudo)
        self.assertEqual(mentoria.modelo, "modelo-teste")
        self.assertIn("gastos_por_categoria", mentoria.dados_enviados)
        self.assertContains(response, "Mentoria financeira da IA atualizada.")

    @override_settings(
        OPENAI_API_KEY="sk-teste",
        OPENAI_MENTORIA_MODEL="modelo-inexistente",
        OPENAI_MENTORIA_FALLBACK_MODEL="gpt-4.1-mini",
    )
    @patch("core.ai_mentoria._post_openai")
    def test_botao_mentoria_ia_usa_fallback_quando_modelo_nao_existe(self, post_openai):
        erro = HTTPError(
            url="https://api.openai.com/v1/responses",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=BytesIO(b'{"error":{"code":"model_not_found","message":"model does not exist"}}'),
        )
        post_openai.side_effect = [
            erro,
            {"output_text": "Análise com fallback.\n1. Ajuste o mercado."},
        ]

        response = self.client.post(reverse("gerar_mentoria_ia"), follow=True)

        self.assertRedirects(response, reverse("dashboard"))
        mentoria = MentoriaFinanceiraIA.objects.get(criado_por=self.user)
        self.assertEqual(mentoria.modelo, "gpt-4.1-mini")
        self.assertIn("Análise com fallback", mentoria.conteudo)

    @override_settings(OPENAI_API_KEY="")
    def test_botao_mentoria_ia_sem_chave_mostra_erro(self):
        response = self.client.post(reverse("gerar_mentoria_ia"), follow=True)

        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(MentoriaFinanceiraIA.objects.filter(criado_por=self.user).exists())
        self.assertContains(response, "Configure OPENAI_API_KEY")

    def test_manual_do_sistema_esta_disponivel(self):
        response = self.client.get(reverse("manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manual")
        self.assertContains(response, "Receitas")
        self.assertContains(response, "Despesas")
        self.assertContains(response, "Controle")
        self.assertContains(response, "compartilhados")

    def test_manual_exibe_legenda_de_icones_sem_textos_longos(self):
        response = self.client.get(reverse("manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ações rápidas")
        self.assertContains(response, "despesa parcelada")
        self.assertNotContains(response, "Visualizar um cadastro sem editar.")
        self.assertNotContains(response, "Abrir relatórios, PDF e Excel do orçamento.")


class InfraestruturaTests(TestCase):
    def test_workflow_de_ci_existe_e_executa_check_e_test(self):
        workflow = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "django.yml"

        self.assertTrue(workflow.exists())
        conteudo = workflow.read_text(encoding="utf-8")
        self.assertIn("python manage.py check", conteudo)
        self.assertIn("python manage.py test", conteudo)

    def test_healthz_retorna_ok_sem_autenticacao(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    @override_settings(HEALTHZ_TOKEN="segredo-monitoramento")
    def test_healthz_com_token_requer_cabecalho_correto(self):
        response_sem_token = self.client.get(reverse("healthz"))
        response_token_invalido = self.client.get(
            reverse("healthz"),
            HTTP_X_HEALTHZ_TOKEN="token-incorreto",
        )
        response_token_valido = self.client.get(
            reverse("healthz"),
            HTTP_X_HEALTHZ_TOKEN="segredo-monitoramento",
        )

        self.assertEqual(response_sem_token.status_code, 404)
        self.assertEqual(response_token_invalido.status_code, 404)
        self.assertEqual(response_token_valido.status_code, 200)
        self.assertJSONEqual(response_token_valido.content, {"status": "ok"})


class FormatacaoTests(TestCase):
    def test_parse_decimal_br_calcula_multiplicacao_e_divisao(self):
        self.assertEqual(parse_decimal_br("100/2"), Decimal("50"))
        self.assertEqual(parse_decimal_br("100*2"), Decimal("200"))
        self.assertEqual(parse_decimal_br("100+50/2"), Decimal("125"))
        self.assertEqual(parse_decimal_br("1.200,00/3"), Decimal("400.00"))
        self.assertEqual(parse_decimal_br("100+50/2+30/3"), Decimal("135"))
        self.assertEqual(parse_decimal_br("1.200+600/3"), Decimal("1400"))
        self.assertEqual(parse_decimal_br("(1.200+600)/3"), Decimal("600"))


class SistemaIndividualTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="usuario_individual",
            password="senha-forte-123",
        )
        self.outro_usuario = get_user_model().objects.create_user(
            username="outro_usuario",
            password="senha-forte-123",
        )
        self.client.force_login(self.user)

        Receita.objects.create(
            descricao="Receita própria",
            valor=Decimal("100.00"),
            data=date(2026, 4, 16),
            criado_por=self.user,
        )
        Receita.objects.create(
            descricao="Receita de outra pessoa",
            valor=Decimal("200.00"),
            data=date(2026, 4, 16),
            criado_por=self.outro_usuario,
        )

    def test_header_nao_exibe_empresa_ou_seletor_de_grupos(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="empresa_id"', html=False)
        self.assertNotContains(response, "Empresa padrão")

    def test_dados_financeiros_sao_filtrados_por_usuario(self):
        response_inicial = self.client.get(reverse("financeiro:receita_lista"))
        self.assertContains(response_inicial, "Receita própria")
        self.assertNotContains(response_inicial, "Receita de outra pessoa")
