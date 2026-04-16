from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Empresa
from financeiro.models import Despesa, Receita


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
        self.assertContains(response, "Resumo da semana")
        self.assertContains(response, "Planejamento semanal")
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

        response = self.client.get(reverse("dashboard"), {"periodo": "todos"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Livre nesta semana")
        self.assertContains(response, "Salário recente")
        self.assertContains(response, "R$ 400,00")
        self.assertIn("planejamento_semanal", response.context)
        lancamentos = [item["descricao"] for item in response.context["ultimos_lancamentos"]]
        self.assertIn("Salário recente", lancamentos)
        self.assertNotIn("Compra cancelada", lancamentos)

    def test_dashboard_permite_navegar_por_semana(self):
        response = self.client.get(reverse("dashboard"), {"semana": "2026-04-20", "periodo": "todos"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "20/04/2026 a 26/04/2026")
        self.assertContains(response, "semana=2026-04-13")
        self.assertContains(response, "semana=2026-04-27")

    def test_manual_do_sistema_esta_disponivel(self):
        response = self.client.get(reverse("manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manual")
        self.assertContains(response, "Receitas")
        self.assertContains(response, "Despesas")
        self.assertContains(response, "Controle")

    def test_manual_exibe_legenda_de_icones_sem_textos_longos(self):
        response = self.client.get(reverse("manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dicas rápidas")
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


class MultiEmpresaAtivaTests(TestCase):
    def setUp(self):
        self.empresa_a = Group.objects.create(name="Empresa A")
        self.empresa_b = Group.objects.create(name="Empresa B")
        self.user = get_user_model().objects.create_user(
            username="usuario_multiempresa",
            password="senha-forte-123",
            perfil="admin",
        )
        self.user.groups.set([self.empresa_a, self.empresa_b])
        self.client.force_login(self.user)

        Receita.objects.create(
            descricao="Receita A",
            valor=Decimal("100.00"),
            data=date(2026, 4, 16),
            empresa=self.empresa_a,
            criado_por=self.user,
        )
        Receita.objects.create(
            descricao="Receita B",
            valor=Decimal("200.00"),
            data=date(2026, 4, 16),
            empresa=self.empresa_b,
            criado_por=self.user,
        )

    def test_header_exibe_seletor_quando_usuario_tem_varias_empresas(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="empresa_id"', html=False)
        self.assertContains(response, "Empresa A")
        self.assertContains(response, "Empresa B")

    def test_trocar_empresa_ativa_altera_isolamento_dos_dados(self):
        response_inicial = self.client.get(reverse("financeiro:receita_lista"))
        self.assertContains(response_inicial, "Receita A")
        self.assertNotContains(response_inicial, "Receita B")

        self.client.post(
            reverse("alternar_empresa"),
            {
                "empresa_id": Empresa.objects.get(grupo=self.empresa_b).pk,
                "next": reverse("financeiro:receita_lista"),
            },
            follow=True,
        )

        response_trocado = self.client.get(reverse("financeiro:receita_lista"))
        self.assertContains(response_trocado, "Receita B")
        self.assertNotContains(response_trocado, "Receita A")
