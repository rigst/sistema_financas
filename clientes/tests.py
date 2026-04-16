from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from orcamentos.models import Orcamento
from .models import Cliente


class ClientePermissaoTests(TestCase):
    def test_visualizador_nao_pode_criar_cliente(self):
        user = get_user_model().objects.create_user(
            username="visualizador",
            password="senha-forte-123",
            perfil="visualizador",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("clientes:criar"))

        self.assertEqual(response.status_code, 403)

    def test_visualizador_nao_pode_excluir_cliente(self):
        user = get_user_model().objects.create_user(
            username="visualizador_delete",
            password="senha-forte-123",
            perfil="visualizador",
        )
        cliente = Cliente.objects.create(nome_razao_social="Cliente Bloqueado")
        self.client.force_login(user)

        response = self.client.get(reverse("clientes:excluir", args=[cliente.pk]))

        self.assertEqual(response.status_code, 403)

    def test_visualizador_nao_ve_atalho_de_novo_cliente(self):
        user = get_user_model().objects.create_user(
            username="visualizador_sem_atalho",
            password="senha-forte-123",
            perfil="visualizador",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("clientes:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("clientes:criar"))


class ClienteValidacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="orc_clientes",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(self.user)

    def test_cliente_invalido_exibe_erros_amigaveis(self):
        response = self.client.post(
            reverse("clientes:criar"),
            {
                "tipo_pessoa": "PF",
                "nome_razao_social": "",
                "cpf_cnpj": "123",
                "telefone": "9999",
                "celular": "8888",
                "cep": "123",
                "estado": "XX",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe o nome ou razão social.")
        self.assertContains(response, "Informe um CPF com 11 dígitos ou um CNPJ com 14 dígitos.")
        self.assertContains(response, "Telefone deve ter 10 ou 11 dígitos, incluindo DDD.")
        self.assertContains(response, "Celular deve ter 10 ou 11 dígitos, incluindo DDD.")
        self.assertContains(response, "CEP deve ter 8 dígitos.")
        self.assertContains(response, "Informe uma UF válida com duas letras.")
        self.assertEqual(Cliente.objects.count(), 0)

    def test_cliente_aceita_campos_com_mascara_e_salva_formatado(self):
        response = self.client.post(
            reverse("clientes:criar"),
            {
                "tipo_pessoa": "PJ",
                "nome_razao_social": "Cliente Mascara",
                "cpf_cnpj": "12.345.678/0001-90",
                "telefone": "(11) 3333-4444",
                "celular": "(11) 98888-7777",
                "cep": "01310-100",
                "estado": "SP",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        cliente = Cliente.objects.get(nome_razao_social="Cliente Mascara")
        self.assertEqual(cliente.cpf_cnpj, "12.345.678/0001-90")
        self.assertEqual(cliente.telefone, "(11) 3333-4444")
        self.assertEqual(cliente.celular, "(11) 98888-7777")
        self.assertEqual(cliente.cep, "01310-100")


class ClienteListaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="lista_clientes",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(self.user)
        Cliente.objects.create(nome_razao_social="Cliente Ativo", cidade="Sao Paulo", ativo=True)
        Cliente.objects.create(nome_razao_social="Cliente Inativo", cidade="Campinas", ativo=False)

    def test_lista_filtra_por_status_ativo(self):
        response = self.client.get(reverse("clientes:lista"), {"ativo": "ativos"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente Ativo")
        self.assertNotContains(response, "Cliente Inativo")

    def test_lista_ordena_por_cidade(self):
        response = self.client.get(reverse("clientes:lista"), {"sort": "cidade", "ativo": "inativos"})

        self.assertEqual(response.status_code, 200)
        clientes = list(response.context["clientes"])
        self.assertEqual(clientes[0].cidade, "Campinas")

    def test_lista_de_clientes_e_paginada(self):
        for indice in range(13):
            Cliente.objects.create(nome_razao_social=f"Cliente Extra {indice:02d}")

        response = self.client.get(reverse("clientes:lista"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_previous())
        self.assertContains(response, "Cliente Extra 12")

    def test_lista_exibe_botao_principal_com_texto(self):
        response = self.client.get(reverse("clientes:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Novo cliente")


class ClienteExclusaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="gerente_clientes",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(self.user)

    def test_cliente_pode_ser_inativado_por_orcamentista(self):
        cliente = Cliente.objects.create(nome_razao_social="Cliente Excluir")

        response = self.client.post(reverse("clientes:excluir", args=[cliente.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente inativado com sucesso.")
        cliente.refresh_from_db()
        self.assertFalse(cliente.ativo)

    def test_cliente_pode_ser_reativado(self):
        cliente = Cliente.objects.create(nome_razao_social="Cliente Vinculado")
        Orcamento.objects.create(
            numero="ORC-CLI-0001",
            cliente=cliente,
            titulo="Orçamento vinculado",
            data_emissao="2026-04-09",
            criado_por=self.user,
            atualizado_por=self.user,
        )

        response = self.client.post(reverse("clientes:excluir", args=[cliente.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        cliente.refresh_from_db()
        self.assertFalse(cliente.ativo)

        response = self.client.post(reverse("clientes:excluir", args=[cliente.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente reativado com sucesso.")
        cliente.refresh_from_db()
        self.assertTrue(cliente.ativo)


class ClienteAtualizacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="editor_clientes",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(self.user)

    def test_formulario_de_edicao_exibe_aviso_sobre_orcamentos_nao_enviados(self):
        cliente = Cliente.objects.create(nome_razao_social="Cliente Base")

        response = self.client.get(reverse("clientes:editar", args=[cliente.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "orçamentos ainda não enviados")
        self.assertContains(response, ">Voltar<", html=False)
        self.assertContains(response, "Salvar cliente")

    def test_edicao_de_cliente_exibe_mensagem_de_propagacao(self):
        cliente = Cliente.objects.create(nome_razao_social="Cliente Base")

        response = self.client.post(
            reverse("clientes:editar", args=[cliente.pk]),
            {
                "tipo_pessoa": cliente.tipo_pessoa,
                "nome_razao_social": "Cliente Atualizado",
                "nome_fantasia": cliente.nome_fantasia,
                "cpf_cnpj": cliente.cpf_cnpj,
                "email": cliente.email,
                "contato_responsavel": cliente.contato_responsavel,
                "telefone": cliente.telefone,
                "celular": cliente.celular,
                "cep": cliente.cep,
                "logradouro": cliente.logradouro,
                "numero": cliente.numero,
                "complemento": cliente.complemento,
                "bairro": cliente.bairro,
                "cidade": cliente.cidade,
                "estado": cliente.estado,
                "observacoes": cliente.observacoes,
                "ativo": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Os orçamentos ainda não enviados passam a usar os dados mais recentes deste cliente.",
        )

    def test_edicao_concorrente_de_cliente_e_bloqueada(self):
        cliente = Cliente.objects.create(nome_razao_social="Cliente Base")
        versao_original = cliente.atualizado_em.isoformat(timespec="microseconds")

        Cliente.objects.filter(pk=cliente.pk).update(
            nome_razao_social="Cliente atualizado em outra sessão",
            atualizado_em=timezone.now(),
        )

        response = self.client.post(
            reverse("clientes:editar", args=[cliente.pk]),
            {
                "tipo_pessoa": cliente.tipo_pessoa,
                "nome_razao_social": "Cliente sobrescrito",
                "nome_fantasia": cliente.nome_fantasia,
                "cpf_cnpj": cliente.cpf_cnpj,
                "email": cliente.email,
                "contato_responsavel": cliente.contato_responsavel,
                "telefone": cliente.telefone,
                "celular": cliente.celular,
                "cep": cliente.cep,
                "logradouro": cliente.logradouro,
                "numero": cliente.numero,
                "complemento": cliente.complemento,
                "bairro": cliente.bairro,
                "cidade": cliente.cidade,
                "estado": cliente.estado,
                "observacoes": cliente.observacoes,
                "ativo": "on",
                "concorrencia_atualizado_em": versao_original,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Este registro foi alterado em outra sessão. Recarregue a página para revisar os dados mais recentes.",
        )
        cliente.refresh_from_db()
        self.assertEqual(cliente.nome_razao_social, "Cliente atualizado em outra sessão")


class ClienteEmpresaIsolationTests(TestCase):
    def setUp(self):
        self.empresa_a = Group.objects.create(name="Empresa A")
        self.empresa_b = Group.objects.create(name="Empresa B")
        self.user_a = get_user_model().objects.create_user(
            username="empresa_a",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.user_a.groups.set([self.empresa_a])
        self.user_b = get_user_model().objects.create_user(
            username="empresa_b",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.user_b.groups.set([self.empresa_b])

        self.cliente_a = Cliente.objects.create(nome_razao_social="Cliente A", empresa=self.empresa_a)
        self.cliente_b = Cliente.objects.create(nome_razao_social="Cliente B", empresa=self.empresa_b)

    def test_lista_mostra_apenas_clientes_da_mesma_empresa(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("clientes:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente A")
        self.assertNotContains(response, "Cliente B")

    def test_usuario_nao_acessa_cliente_de_outra_empresa(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("clientes:visualizar", args=[self.cliente_b.pk]))

        self.assertEqual(response.status_code, 404)
