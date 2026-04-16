from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from orcamentos.models import Orcamento
from relatorios.models import ConfiguracaoEmpresa
from .views import UsuarioLoginView


class AdminPermissaoPerfilTests(TestCase):
    def criar_usuario(self, username, perfil):
        return get_user_model().objects.create_user(
            username=username,
            password="senha-forte-123",
            perfil=perfil,
            is_staff=True,
        )

    def test_admin_tem_acesso_ao_admin_de_usuarios(self):
        user = self.criar_usuario("admin", "admin")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:usuarios_usuario_changelist"))

        self.assertEqual(response.status_code, 200)

    def test_orcamentista_nao_tem_acesso_ao_admin_de_usuarios(self):
        user = self.criar_usuario("orcamentista", "orcamentista")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:usuarios_usuario_changelist"))

        self.assertEqual(response.status_code, 403)

    def test_orcamentista_pode_gerenciar_clientes_no_admin(self):
        user = self.criar_usuario("orc_clientes", "orcamentista")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:clientes_cliente_add"))

        self.assertEqual(response.status_code, 200)

    def test_orcamentista_nao_pode_gerenciar_catalogo_no_admin(self):
        user = self.criar_usuario("orc_catalogo", "orcamentista")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:catalogo_itemcatalogo_add"))

        self.assertEqual(response.status_code, 403)

    def test_visualizador_pode_ver_orcamentos_no_admin_mas_nao_criar(self):
        user = self.criar_usuario("visualizador", "visualizador")
        self.client.force_login(user)

        changelist_response = self.client.get(reverse("admin:orcamentos_orcamento_changelist"))
        add_response = self.client.get(reverse("admin:orcamentos_orcamento_add"))

        self.assertEqual(changelist_response.status_code, 200)
        self.assertEqual(add_response.status_code, 403)

    def test_admin_de_empresa_so_ve_o_proprio_grupo_no_admin(self):
        user = self.criar_usuario("admin_empresa", "admin")
        Group.objects.create(name="Empresa B")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:auth_group_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Empresa padr")
        self.assertNotContains(response, "Empresa B")

    def test_admin_de_empresa_edita_grupo_como_empresa_sem_permissoes_globais(self):
        user = self.criar_usuario("admin_grupo", "admin")
        grupo = user.groups.get()
        self.client.force_login(user)

        response = self.client.get(reverse("admin:auth_group_change", args=[grupo.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cada grupo representa uma empresa isolada das demais no sistema.")
        self.assertContains(response, 'for="id_name"', html=False)
        self.assertNotContains(response, 'id_permissions')

    def test_superusuario_com_perfil_padrao_acessa_telas_restritas_do_admin(self):
        user = get_user_model().objects.create_superuser(
            username="root_admin",
            email="root_admin@example.com",
            password="senha-forte-123",
        )
        self.client.force_login(user)

        response_usuarios = self.client.get(reverse("admin:usuarios_usuario_add"))
        response_categoria = self.client.get(reverse("admin:catalogo_categoriaitem_add"))
        response_item = self.client.get(reverse("admin:catalogo_itemcatalogo_add"))
        response_empresa = self.client.get(reverse("admin:relatorios_configuracaoempresa_add"))

        self.assertEqual(response_usuarios.status_code, 200)
        self.assertEqual(response_categoria.status_code, 200)
        self.assertEqual(response_item.status_code, 200)
        self.assertEqual(response_empresa.status_code, 200)


class UsuarioPermissaoPropriedadesTests(TestCase):
    def test_admin_tem_capacidades_de_gestao(self):
        user = get_user_model().objects.create_user(
            username="admin_props",
            password="senha-forte-123",
            perfil="admin",
        )

        self.assertTrue(user.pode_gerenciar_clientes)
        self.assertTrue(user.pode_gerenciar_catalogo)
        self.assertTrue(user.pode_gerenciar_relatorios)
        self.assertTrue(user.pode_gerenciar_orcamentos)

    def test_visualizador_fica_apenas_com_visualizacao(self):
        user = get_user_model().objects.create_user(
            username="vis_props",
            password="senha-forte-123",
            perfil="visualizador",
        )

        self.assertTrue(user.pode_visualizar_clientes)
        self.assertTrue(user.pode_visualizar_catalogo)
        self.assertTrue(user.pode_visualizar_relatorios)
        self.assertTrue(user.pode_visualizar_orcamentos)
        self.assertFalse(user.pode_gerenciar_clientes)
        self.assertFalse(user.pode_gerenciar_catalogo)
        self.assertFalse(user.pode_gerenciar_relatorios)
        self.assertFalse(user.pode_gerenciar_orcamentos)

    def test_superusuario_com_perfil_padrao_tem_capacidades_de_admin(self):
        user = get_user_model().objects.create_superuser(
            username="super_props",
            email="super_props@example.com",
            password="senha-forte-123",
        )

        self.assertTrue(user.eh_admin_perfil)
        self.assertTrue(user.pode_gerenciar_clientes)
        self.assertTrue(user.pode_gerenciar_catalogo)
        self.assertTrue(user.pode_gerenciar_relatorios)
        self.assertTrue(user.pode_gerenciar_orcamentos)


class UsuarioVisitanteTests(TestCase):
    def test_tela_de_login_exibe_acesso_visitante_separado_e_aviso_de_projeto(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrar como visitante")
        self.assertContains(response, "cria um perfil temporário automaticamente")
        self.assertContains(response, "projeto com foco em aprendizado e portfólio")

    def test_login_como_visitante_cria_usuario_temporario_e_remove_no_logout(self):
        response = self.client.post(reverse("login"), {"entrar_visitante": "1"})

        self.assertEqual(response.status_code, 302)
        visitante = get_user_model().objects.get(perfil="visitante")
        grupo = visitante.groups.get()
        self.assertTrue(grupo.name.startswith("__visitante__"))

        self.client.post(reverse("logout"))

        self.assertFalse(get_user_model().objects.filter(pk=visitante.pk).exists())
        self.assertFalse(Group.objects.filter(pk=grupo.pk).exists())

    def test_visitante_exibe_nomes_amigaveis(self):
        self.client.post(reverse("login"), {"entrar_visitante": "1"})

        visitante = get_user_model().objects.get(perfil="visitante")

        self.assertEqual(str(visitante), "Visitante")
        self.assertEqual(visitante.nome_empresa, "Empresa Visitante")

    def test_visitante_nao_ve_dados_de_outra_empresa(self):
        empresa = Group.objects.create(name="Empresa Real")
        usuario = get_user_model().objects.create_user(
            username="empresa_real",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        usuario.groups.set([empresa])
        cliente = Cliente.objects.create(nome_razao_social="Cliente Sigiloso", empresa=empresa)
        Orcamento.objects.create(
            numero="ORC-2026-0009",
            cliente=cliente,
            titulo="Orcamento Sigiloso",
            data_emissao="2026-04-11",
            empresa=empresa,
            criado_por=usuario,
            atualizado_por=usuario,
        )
        ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa Sigilosa", empresa=empresa)

        self.client.post(reverse("login"), {"entrar_visitante": "1"})

        response_clientes = self.client.get(reverse("clientes:lista"))
        response_dashboard = self.client.get(reverse("dashboard"))
        response_relatorios = self.client.get(reverse("relatorios:configuracao_lista"))
        response_cliente_direto = self.client.get(reverse("clientes:visualizar", args=[cliente.pk]))

        self.assertEqual(response_clientes.status_code, 200)
        self.assertNotContains(response_clientes, "Cliente Sigiloso")
        self.assertEqual(response_dashboard.status_code, 200)
        self.assertNotContains(response_dashboard, "Orcamento Sigiloso")
        self.assertNotContains(response_dashboard, "Cliente Sigiloso")
        self.assertEqual(response_relatorios.status_code, 200)
        self.assertNotContains(response_relatorios, "Empresa Sigilosa")
        self.assertEqual(response_cliente_direto.status_code, 404)


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
