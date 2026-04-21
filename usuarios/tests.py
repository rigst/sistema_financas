from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import NoReverseMatch, reverse

from financeiro.models import Despesa, Receita
from .views import UsuarioLoginView


class AdminIndividualTests(TestCase):
    def criar_usuario(self, username, *, staff=True, superuser=False):
        return get_user_model().objects.create_user(
            username=username,
            password="senha-forte-123",
            is_staff=staff,
            is_superuser=superuser,
        )

    def test_superusuario_tem_acesso_ao_admin_de_usuarios(self):
        user = self.criar_usuario("admin", superuser=True)
        self.client.force_login(user)

        response = self.client.get(reverse("admin:usuarios_usuario_changelist"))

        self.assertEqual(response.status_code, 200)

    def test_usuario_staff_comum_nao_administra_usuarios(self):
        user = self.criar_usuario("staff_comum")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:usuarios_usuario_changelist"))

        self.assertEqual(response.status_code, 403)

    def test_usuario_staff_pode_gerenciar_financeiro_no_admin(self):
        user = self.criar_usuario("staff_financeiro")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:financeiro_receita_add"))

        self.assertEqual(response.status_code, 200)

    def test_grupos_nao_aparecem_no_admin_do_sistema_individual(self):
        user = self.criar_usuario("admin_grupos", superuser=True)
        self.client.force_login(user)

        with self.assertRaises(NoReverseMatch):
            reverse("admin:auth_group_changelist")

    def test_admin_de_usuario_nao_exibe_grupos_permissoes_ou_perfil(self):
        user = self.criar_usuario("admin_usuario", superuser=True)
        self.client.force_login(user)

        response = self.client.get(reverse("admin:usuarios_usuario_change", args=[user.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="groups"', html=False)
        self.assertNotContains(response, 'name="user_permissions"', html=False)
        self.assertNotContains(response, 'name="perfil"', html=False)


class UsuarioVisitanteTests(TestCase):
    def test_tela_de_login_exibe_acesso_visitante_separado_e_aviso_de_projeto(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrar como visitante")
        self.assertContains(response, "cria um usuário temporário automaticamente")
        self.assertContains(response, "projeto com foco em aprendizado e portfólio")

    def test_login_como_visitante_cria_usuario_temporario_e_remove_no_logout(self):
        response = self.client.post(reverse("login"), {"entrar_visitante": "1"})

        self.assertEqual(response.status_code, 302)
        visitante = get_user_model().objects.get(username__startswith="visitante_")
        self.assertEqual(str(visitante), "Visitante")

        self.client.post(reverse("logout"))

        self.assertFalse(get_user_model().objects.filter(pk=visitante.pk).exists())

    def test_visitante_nao_ve_dados_de_outro_usuario(self):
        usuario = get_user_model().objects.create_user(
            username="usuario_real",
            password="senha-forte-123",
        )
        Receita.objects.create(
            descricao="Receita Sigilosa",
            valor=Decimal("500.00"),
            data=date(2026, 4, 10),
            criado_por=usuario,
        )
        Despesa.objects.create(
            descricao="Pagamento Sigiloso",
            valor=Decimal("120.00"),
            data=date(2026, 4, 11),
            tipo="variavel",
            categoria="Despesa Sigilosa",
            criado_por=usuario,
        )

        self.client.post(reverse("login"), {"entrar_visitante": "1"})

        response_receitas = self.client.get(reverse("financeiro:receita_lista"))
        response_despesas = self.client.get(reverse("financeiro:despesa_lista"))
        response_dashboard = self.client.get(reverse("dashboard"))

        self.assertEqual(response_receitas.status_code, 200)
        self.assertNotContains(response_receitas, "Receita Sigilosa")
        self.assertEqual(response_despesas.status_code, 200)
        self.assertNotContains(response_despesas, "Pagamento Sigiloso")
        self.assertEqual(response_dashboard.status_code, 200)
        self.assertNotContains(response_dashboard, "Pagamento Sigiloso")
        self.assertNotContains(response_dashboard, "Receita Sigilosa")


class UsuarioVisitanteIpTests(TestCase):
    def test_login_visitante_usa_ultimo_ip_de_x_forwarded_for(self):
        request = RequestFactory().post(
            reverse("login"),
            HTTP_X_FORWARDED_FOR="198.51.100.10, 203.0.113.77",
        )
        view = UsuarioLoginView()
        view.request = request

        self.assertEqual(view._client_ip(), "203.0.113.77")

    def test_login_visitante_cai_para_remote_addr_sem_x_forwarded_for(self):
        request = RequestFactory().post(
            reverse("login"),
            REMOTE_ADDR="10.0.0.5",
        )
        view = UsuarioLoginView()
        view.request = request

        self.assertEqual(view._client_ip(), "10.0.0.5")
