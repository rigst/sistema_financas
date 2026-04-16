from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from core.models import Empresa
from orcamentos.models import Orcamento


class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dashboard_user",
            password="senha-forte-123",
        )
        self.client.force_login(self.user)
        self.cliente = Cliente.objects.create(nome_razao_social="Cliente Dashboard")

        Orcamento.objects.create(
            numero="ORC-DASH-1",
            cliente=self.cliente,
            titulo="Aprovado recente",
            status="aprovado",
            data_emissao=timezone.localdate(),
            total_final=Decimal("1200.00"),
            criado_por=self.user,
            atualizado_por=self.user,
        )
        Orcamento.objects.create(
            numero="ORC-DASH-2",
            cliente=self.cliente,
            titulo="Rascunho antigo",
            status="rascunho",
            data_emissao=timezone.localdate() - timedelta(days=45),
            total_final=Decimal("800.00"),
            criado_por=self.user,
            atualizado_por=self.user,
        )

    def test_dashboard_filtra_periodo_e_exibe_indicadores(self):
        response = self.client.get(reverse("dashboard"), {"periodo": "30"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "R$ 1.200,00")
        self.assertContains(response, "Últimos 30 dias")
        self.assertNotContains(response, "Rascunho antigo")

    def test_dashboard_oculta_cancelados_rejeitados_e_inativos_dos_ultimos_orcamentos(self):
        Orcamento.objects.create(
            numero="ORC-DASH-3",
            cliente=self.cliente,
            titulo="Rejeitado recente",
            status="rejeitado",
            data_emissao=timezone.localdate(),
            total_final=Decimal("300.00"),
            criado_por=self.user,
            atualizado_por=self.user,
        )
        Orcamento.objects.create(
            numero="ORC-DASH-4",
            cliente=self.cliente,
            titulo="Cancelado recente",
            status="cancelado",
            data_emissao=timezone.localdate(),
            total_final=Decimal("400.00"),
            criado_por=self.user,
            atualizado_por=self.user,
        )
        Orcamento.objects.create(
            numero="ORC-DASH-5",
            cliente=self.cliente,
            titulo="Inativo recente",
            status="aprovado",
            ativo=False,
            data_emissao=timezone.localdate(),
            total_final=Decimal("500.00"),
            criado_por=self.user,
            atualizado_por=self.user,
        )

        response = self.client.get(reverse("dashboard"), {"periodo": "todos"})

        self.assertEqual(response.status_code, 200)
        titulos = [orcamento.titulo for orcamento in response.context["ultimos_orcamentos"]]
        self.assertIn("Aprovado recente", titulos)
        self.assertNotIn("Rejeitado recente", titulos)
        self.assertNotIn("Cancelado recente", titulos)
        self.assertNotIn("Inativo recente", titulos)

    def test_manual_do_sistema_esta_disponivel(self):
        response = self.client.get(reverse("manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manual do sistema")
        self.assertContains(response, "Perfis e autorizações")

    def test_manual_exibe_legenda_de_icones_sem_textos_longos(self):
        response = self.client.get(reverse("manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Legenda dos ícones")
        self.assertContains(response, "Visualizar")
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

        Cliente.objects.create(nome_razao_social="Cliente A", empresa=self.empresa_a)
        Cliente.objects.create(nome_razao_social="Cliente B", empresa=self.empresa_b)

    def test_header_exibe_seletor_quando_usuario_tem_varias_empresas(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="empresa_id"', html=False)
        self.assertContains(response, "Empresa A")
        self.assertContains(response, "Empresa B")

    def test_trocar_empresa_ativa_altera_isolamento_dos_dados(self):
        response_inicial = self.client.get(reverse("clientes:lista"))
        self.assertContains(response_inicial, "Cliente A")
        self.assertNotContains(response_inicial, "Cliente B")

        self.client.post(
            reverse("alternar_empresa"),
            {
                "empresa_id": Empresa.objects.get(grupo=self.empresa_b).pk,
                "next": reverse("clientes:lista"),
            },
            follow=True,
        )

        response_trocado = self.client.get(reverse("clientes:lista"))
        self.assertContains(response_trocado, "Cliente B")
        self.assertNotContains(response_trocado, "Cliente A")
