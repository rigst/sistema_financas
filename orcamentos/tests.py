from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.models import CategoriaItem, ItemCatalogo
from clientes.models import Cliente
from relatorios.models import ConfiguracaoEmpresa
from .models import ItemOrcamento, Orcamento


class OrcamentoViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            password="senha-forte-123",
        )
        self.client.force_login(self.user)

        self.cliente = Cliente.objects.create(nome_razao_social="Cliente Teste")
        self.orcamento = Orcamento.objects.create(
            numero="ORC-2026-0001",
            cliente=self.cliente,
            titulo="Orcamento teste",
            data_emissao=date(2026, 4, 9),
            criado_por=self.user,
            atualizado_por=self.user,
        )

    def test_alterar_status_exige_post(self):
        response = self.client.get(
            reverse("orcamentos:alterar_status", args=[self.orcamento.pk, "enviado"])
        )

        self.assertEqual(response.status_code, 405)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, "rascunho")

    def test_alterar_status_via_post(self):
        response = self.client.post(
            reverse("orcamentos:alterar_status", args=[self.orcamento.pk, "aprovado"])
        )

        self.assertRedirects(response, reverse("orcamentos:lista"))
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, "aprovado")

    def test_alterar_status_invalido_nao_quebra_fluxo(self):
        response = self.client.post(
            reverse("orcamentos:alterar_status", args=[self.orcamento.pk, "status_inexistente"]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Status solicitado é inválido.")
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, "rascunho")

    def test_orcamento_aprovado_nao_volta_para_rascunho_para_nao_admin(self):
        self.orcamento.status = "aprovado"
        self.orcamento.save(update_fields=["status", "atualizado_em"])

        response = self.client.post(
            reverse("orcamentos:alterar_status", args=[self.orcamento.pk, "rascunho"]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "só podem ser reabertos ou alterados por administradores")
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, "aprovado")

    def test_admin_pode_reabrir_orcamento_aprovado_para_rascunho(self):
        admin = get_user_model().objects.create_user(
            username="admin_orcamento",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(admin)
        self.orcamento.status = "aprovado"
        self.orcamento.save(update_fields=["status", "atualizado_em"])

        response = self.client.post(reverse("orcamentos:alterar_status", args=[self.orcamento.pk, "rascunho"]))

        self.assertRedirects(response, reverse("orcamentos:lista"))
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, "rascunho")

    def test_item_invalido_retorna_form_com_erro(self):
        response = self.client.post(
            reverse("orcamentos:item_criar", args=[self.orcamento.pk]),
            {
                "ordem": "abc",
                "nome": "",
                "quantidade": "xpto",
                "valor_unitario": "10.00",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Este campo é obrigatório.", response.json()["modal_html"])
        self.assertEqual(ItemOrcamento.objects.count(), 0)

    def test_item_catalogo_preenche_campos_faltantes(self):
        item_catalogo = ItemCatalogo.objects.create(
            codigo="SERV-01",
            nome="Servico",
            descricao_padrao="Descricao padrao",
            unidade_medida="sv",
            valor_unitario_padrao=Decimal("125.50"),
        )

        response = self.client.post(
            reverse("orcamentos:item_criar", args=[self.orcamento.pk]),
            {
                "item_catalogo": item_catalogo.pk,
                "ordem": 1,
                "codigo_item": "",
                "nome": "",
                "descricao": "",
                "unidade_medida": "",
                "quantidade": "2",
                "valor_unitario": "",
                "desconto_valor": "0",
                "desconto_percentual": "0",
                "acrescimo_valor": "0",
                "acrescimo_percentual": "0",
                "observacoes": "",
            },
        )

        self.assertRedirects(response, reverse("orcamentos:editar", args=[self.orcamento.pk]))

        item = ItemOrcamento.objects.get()
        self.assertEqual(item.codigo_item, "ORC-2026-0001-ITEM-001")
        self.assertEqual(item.nome, "Servico")
        self.assertEqual(item.descricao, "Descricao padrao")
        self.assertEqual(item.unidade_medida, "sv")
        self.assertEqual(item.valor_unitario, Decimal("125.50"))

    def test_edicao_concorrente_de_item_orcamento_e_bloqueada(self):
        item_catalogo = ItemCatalogo.objects.create(
            codigo="SERV-CONC",
            nome="Servico concorrente",
            descricao_padrao="Descricao original",
            unidade_medida="sv",
            valor_unitario_padrao=Decimal("100.00"),
        )
        item = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            item_catalogo=item_catalogo,
            ordem=1,
            nome="Servico concorrente",
            descricao="Descricao original",
            unidade_medida="sv",
            quantidade=Decimal("1.00"),
            valor_unitario=Decimal("100.00"),
        )
        versao_original = item.atualizado_em.isoformat(timespec="microseconds")

        ItemOrcamento.objects.filter(pk=item.pk).update(
            nome="Atualizado por outra sessão",
            atualizado_em=timezone.now(),
        )

        response = self.client.post(
            reverse("orcamentos:item_editar", args=[self.orcamento.pk, item.pk]),
            {
                "item_catalogo": item_catalogo.pk,
                "ordem": "1",
                "codigo_item": item.codigo_item,
                "nome": "Tentativa de sobrescrever",
                "descricao": "Descricao tentativa",
                "unidade_medida": "sv",
                "quantidade": "1",
                "valor_unitario": "100.00",
                "desconto_valor": "0",
                "desconto_percentual": "0",
                "acrescimo_valor": "0",
                "acrescimo_percentual": "0",
                "observacoes": "",
                "item_q": "",
                "item_categoria": "",
                "item_sort": "ordem",
                "concorrencia_atualizado_em": versao_original,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Este registro foi alterado em outra sessão. Recarregue a página para revisar os dados mais recentes.",
            response.json()["modal_html"],
        )
        item.refresh_from_db()
        self.assertEqual(item.nome, "Atualizado por outra sessão")

    def test_item_vinculado_ao_catalogo_marca_divergencia_quando_nome_ou_valor_mudam(self):
        item_catalogo = ItemCatalogo.objects.create(
            codigo="CAT-ORIG",
            nome="Servico original",
            descricao_padrao="Descricao base",
            unidade_medida="sv",
            valor_unitario_padrao=Decimal("125.50"),
        )
        item = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            item_catalogo=item_catalogo,
            ordem=1,
            nome="Servico customizado",
            unidade_medida="sv",
            valor_unitario=Decimal("150.00"),
            quantidade=Decimal("1.00"),
        )

        self.assertTrue(item.diverge_catalogo)
        self.assertEqual(item.campos_divergentes_catalogo(), ["nome", "valor"])

    def test_campos_de_ajuste_nao_sao_obrigatorios_no_formulario(self):
        response = self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Desconto global em valor<span class=\"required-mark\">*</span>", html=True)
        self.assertNotContains(response, "Desconto global em %<span class=\"required-mark\">*</span>", html=True)
        self.assertNotContains(response, "Acréscimo global em valor<span class=\"required-mark\">*</span>", html=True)
        self.assertNotContains(response, "Acréscimo global em %<span class=\"required-mark\">*</span>", html=True)

    def test_orcamento_novo_recebe_numero_automatico(self):
        response = self.client.post(
            reverse("orcamentos:criar"),
            {
                "numero": "",
                "cliente": self.cliente.pk,
                "titulo": "Novo orçamento automático",
                "descricao_inicial": "",
                "observacoes_gerais": "",
                "status": "rascunho",
                "data_emissao": "2026-04-09",
                "validade_em": "",
                "desconto_global_valor": "0.00",
                "desconto_global_percentual": "0.00",
                "acrescimo_global_valor": "0.00",
                "acrescimo_global_percentual": "0.00",
                "mostrar_ajustes_no_relatorio": "",
            },
        )

        novo = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        self.assertRedirects(response, reverse("orcamentos:editar", args=[novo.pk]))
        self.assertEqual(novo.numero, "ORC-2026-0002")

    def test_orcamento_pode_selecionar_configuracao_da_empresa_e_puxar_validade_padrao(self):
        configuracao_padrao = ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa Base",
            validade_padrao_proposta="15 dias",
        )
        outra_configuracao = ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa Secundaria",
            validade_padrao_proposta="30",
        )

        response = self.client.post(
            reverse("orcamentos:criar"),
            {
                "numero": "",
                "configuracao_empresa": outra_configuracao.pk,
                "cliente": self.cliente.pk,
                "titulo": "Orçamento com empresa selecionada",
                "descricao_inicial": "",
                "observacoes_gerais": "",
                "status": "rascunho",
                "data_emissao": "2026-04-09",
                "validade_em": "",
                "desconto_global_valor": "0.00",
                "desconto_global_percentual": "0.00",
                "acrescimo_global_valor": "0.00",
                "acrescimo_global_percentual": "0.00",
                "mostrar_ajustes_no_relatorio": "",
            },
        )

        novo = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        self.assertRedirects(response, reverse("orcamentos:editar", args=[novo.pk]))
        self.assertEqual(novo.configuracao_empresa_id, outra_configuracao.pk)
        self.assertEqual(novo.validade_em.isoformat(), "2026-05-09")
        self.assertNotEqual(novo.configuracao_empresa_id, configuracao_padrao.pk)

    def test_orcamento_aceita_campos_de_evento_comercial_e_contrato(self):
        response = self.client.post(
            reverse("orcamentos:editar", args=[self.orcamento.pk]),
            {
                "numero": self.orcamento.numero,
                "cliente": self.cliente.pk,
                "titulo": self.orcamento.titulo,
                "descricao_inicial": "",
                "observacoes_gerais": "Observacoes gerais do projeto",
                "status": self.orcamento.status,
                "data_emissao": self.orcamento.data_emissao.isoformat(),
                "validade_em": "2026-04-20",
                "evento_nome": "Expointer 2026",
                "evento_periodo": "24/08 a 01/09/2026",
                "evento_local": "Esteio/RS",
                "evento_estande": "A12",
                "evento_area": "120m2",
                "evento_contato": "Maria Silva",
                "evento_telefone": "(51) 99999-0000",
                "evento_email": "evento@cliente.com",
                "desconto_global_valor": "0.00",
                "desconto_global_percentual": "0.00",
                "acrescimo_global_valor": "0.00",
                "acrescimo_global_percentual": "0.00",
                "condicoes_pagamento": "50% na assinatura e 50% na entrega",
                "valor_locacao": "1000.00",
                "valor_servico": "500.00",
                "servicos_taxas_inclusos": "Montagem e desmontagem",
                "contrato_razao_social": "Cliente Teste LTDA",
                "contrato_cnpj": "12.345.678/0001-90",
                "contrato_endereco": "Rua A, 100",
                "contrato_cidade": "Porto Alegre",
                "contrato_cep": "90000-000",
                "contrato_responsavel_nome": "Joao Responsavel",
                "contrato_responsavel_documento": "RG 123 / CPF 000",
                "contrato_cargo_funcao": "Diretor",
                "contrato_telefone": "(51) 98888-0000",
                "contrato_email": "contrato@cliente.com",
                "contrato_inscricao_estadual": "123456789",
                "mostrar_ajustes_no_relatorio": "on",
            },
        )

        self.assertRedirects(response, reverse("orcamentos:editar", args=[self.orcamento.pk]))
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.evento_nome, "Expointer 2026")
        self.assertEqual(self.orcamento.evento_telefone, "(51) 99999-0000")
        self.assertEqual(self.orcamento.condicoes_pagamento, "50% na assinatura e 50% na entrega")
        self.assertEqual(self.orcamento.valor_locacao, Decimal("1000.00"))
        self.assertEqual(self.orcamento.valor_servico, Decimal("500.00"))
        self.assertEqual(self.orcamento.contrato_cnpj, "12.345.678/0001-90")
        self.assertEqual(self.orcamento.contrato_cep, "90000-000")

    def test_item_recebe_codigo_automatico_mesmo_sem_codigo_informado(self):
        response = self.client.post(
            reverse("orcamentos:item_criar", args=[self.orcamento.pk]),
            {
                "ordem": 1,
                "codigo_item": "",
                "nome": "Item automático",
                "descricao": "",
                "unidade_medida": "un",
                "quantidade": "1",
                "valor_unitario": "10.00",
                "desconto_valor": "0",
                "desconto_percentual": "0",
                "acrescimo_valor": "0",
                "acrescimo_percentual": "0",
                "observacoes": "",
            },
        )

        item = ItemOrcamento.objects.get(nome="Item automático")
        self.assertRedirects(response, reverse("orcamentos:editar", args=[self.orcamento.pk]))
        self.assertEqual(item.codigo_item, "ORC-2026-0001-ITEM-001")

    def test_item_do_catalogo_aceita_valor_zero_informado_manualmente(self):
        item_catalogo = ItemCatalogo.objects.create(
            codigo="SERV-ZERO",
            nome="Servico zero",
            unidade_medida="sv",
            valor_unitario_padrao=Decimal("125.50"),
        )

        response = self.client.post(
            reverse("orcamentos:item_criar", args=[self.orcamento.pk]),
            {
                "item_catalogo": item_catalogo.pk,
                "descricao": "",
                "quantidade": "2",
                "valor_unitario": "0",
                "desconto_valor": "0",
                "desconto_percentual": "0",
                "acrescimo_valor": "0",
                "acrescimo_percentual": "0",
            },
        )

        self.assertRedirects(response, reverse("orcamentos:editar", args=[self.orcamento.pk]))
        item = ItemOrcamento.objects.get()
        self.assertEqual(item.valor_unitario, Decimal("0.00"))
        self.assertEqual(item.subtotal, Decimal("0.00"))

    def test_item_importado_do_catalogo_nao_marca_personalizacao_sem_edicao(self):
        categoria = CategoriaItem.objects.create(nome="Piso importado")
        item_catalogo = ItemCatalogo.objects.create(
            codigo="IMP-01",
            nome="Brita (camada de 2cm)",
            categoria=categoria,
            unidade_medida="m2",
            valor_unitario_padrao=Decimal("85.71"),
        )

        response = self.client.post(
            reverse("orcamentos:item_criar", args=[self.orcamento.pk]),
            {
                "item_catalogo": item_catalogo.pk,
                "ordem": 1,
                "codigo_item": "",
                "nome": "",
                "descricao": "",
                "unidade_medida": "",
                "quantidade": "1",
                "valor_unitario": "",
                "desconto_valor": "0",
                "desconto_percentual": "0",
                "acrescimo_valor": "0",
                "acrescimo_percentual": "0",
                "observacoes": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Personalizado em relação ao catálogo")
        item = ItemOrcamento.objects.get()
        self.assertFalse(item.diverge_catalogo)

    def test_visualizador_pode_ver_orcamento_em_modo_somente_leitura(self):
        visualizador = get_user_model().objects.create_user(
            username="visualizador",
            password="senha-forte-123",
            perfil="visualizador",
        )
        self.client.force_login(visualizador)

        response = self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "modo somente leitura")

    def test_visualizacao_dedicada_bloqueia_edicao_geral_e_itens(self):
        item = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            nome="Item somente leitura",
            unidade_medida="un",
            quantidade=Decimal("2.00"),
            valor_unitario=Decimal("15.00"),
        )

        response = self.client.get(reverse("orcamentos:visualizar", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "modo estritamente visual")
        self.assertContains(response, "Esta tela é exclusiva para consulta e não permite alterações.")
        self.assertNotContains(response, "Salvar orçamento")
        self.assertNotContains(response, "Adicionar item")
        self.assertNotContains(response, reverse("orcamentos:item_editar", args=[self.orcamento.pk, item.pk]))
        self.assertNotContains(response, reverse("orcamentos:item_excluir", args=[self.orcamento.pk, item.pk]))

    def test_visualizador_da_lista_aponta_para_rota_de_visualizacao(self):
        visualizador = get_user_model().objects.create_user(
            username="visualizador_lista_link",
            password="senha-forte-123",
            perfil="visualizador",
        )
        self.client.force_login(visualizador)

        response = self.client.get(reverse("orcamentos:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("orcamentos:visualizar", args=[self.orcamento.pk]))
        self.assertNotContains(response, reverse("orcamentos:editar", args=[self.orcamento.pk]))

    def test_lista_exibe_botao_principal_novo_orcamento_com_texto(self):
        response = self.client.get(reverse("orcamentos:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("orcamentos:criar"))
        self.assertContains(response, "Novo orçamento")

    def test_visualizador_nao_ve_botoes_de_edicao_na_lista(self):
        visualizador = get_user_model().objects.create_user(
            username="visualizador_lista",
            password="senha-forte-123",
            perfil="visualizador",
        )
        self.client.force_login(visualizador)

        response = self.client.get(reverse("orcamentos:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("orcamentos:criar"))
        self.assertNotContains(response, reverse("orcamentos:excluir", args=[self.orcamento.pk]))

    def test_visualizador_nao_pode_salvar_orcamento(self):
        visualizador = get_user_model().objects.create_user(
            username="visualizador2",
            password="senha-forte-123",
            perfil="visualizador",
        )
        self.client.force_login(visualizador)

        response = self.client.post(
            reverse("orcamentos:editar", args=[self.orcamento.pk]),
            {
                "numero": self.orcamento.numero,
                "cliente": self.cliente.pk,
                "titulo": "Titulo alterado",
                "descricao_inicial": "",
                "observacoes_gerais": "",
                "status": self.orcamento.status,
                "data_emissao": self.orcamento.data_emissao.isoformat(),
                "validade_em": "",
                "desconto_global_valor": "0.00",
                "desconto_global_percentual": "0.00",
                "acrescimo_global_valor": "0.00",
                "acrescimo_global_percentual": "0.00",
                "mostrar_ajustes_no_relatorio": "",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_orcamentista_ve_orcamento_aprovado_em_modo_somente_leitura(self):
        self.orcamento.status = "aprovado"
        self.orcamento.save(update_fields=["status", "atualizado_em"])

        response = self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Somente orçamentos em rascunho podem ser editados nesta página.")
        self.assertNotContains(response, "Adicionar item")

    def test_orcamento_fora_de_rascunho_fica_em_modo_somente_leitura_na_edicao(self):
        for status in ("enviado", "aprovado", "rejeitado", "cancelado"):
            with self.subTest(status=status):
                self.orcamento.status = status
                self.orcamento.save(update_fields=["status", "atualizado_em"])

                response = self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Somente orçamentos em rascunho podem ser editados nesta página.")
                self.assertNotContains(response, "Adicionar item")

    def test_orcamento_fora_de_rascunho_nao_pode_salvar_edicao(self):
        self.orcamento.status = "enviado"
        self.orcamento.save(update_fields=["status", "atualizado_em"])

        response = self.client.post(
            reverse("orcamentos:editar", args=[self.orcamento.pk]),
            {
                "numero": self.orcamento.numero,
                "cliente": self.cliente.pk,
                "titulo": "Titulo alterado",
                "descricao_inicial": "",
                "observacoes_gerais": "",
                "status": self.orcamento.status,
                "data_emissao": self.orcamento.data_emissao.isoformat(),
                "validade_em": "",
                "desconto_global_valor": "0.00",
                "desconto_global_percentual": "0.00",
                "acrescimo_global_valor": "0.00",
                "acrescimo_global_percentual": "0.00",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_item_nao_pode_ser_criado_em_orcamento_fora_de_rascunho(self):
        self.orcamento.status = "enviado"
        self.orcamento.save(update_fields=["status", "atualizado_em"])

        response = self.client.post(
            reverse("orcamentos:item_criar", args=[self.orcamento.pk]),
            {
                "nome": "Item bloqueado",
                "quantidade": "1",
                "valor_unitario": "10.00",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(ItemOrcamento.objects.count(), 0)

    def test_orcamento_invalido_exibe_erro_para_usuario(self):
        response = self.client.post(
            reverse("orcamentos:editar", args=[self.orcamento.pk]),
            {
                "numero": self.orcamento.numero,
                "cliente": self.cliente.pk,
                "titulo": "Titulo invalido",
                "descricao_inicial": "",
                "observacoes_gerais": "",
                "status": self.orcamento.status,
                "data_emissao": "2026-04-10",
                "validade_em": "2026-04-09",
                "desconto_global_valor": "0.00",
                "desconto_global_percentual": "0.00",
                "acrescimo_global_valor": "0.00",
                "acrescimo_global_percentual": "0.00",
                "mostrar_ajustes_no_relatorio": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A validade não pode ser anterior à data de emissão.")

    def test_item_pode_ser_duplicado(self):
        item = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            codigo_item="SERV-01",
            nome="Servico base",
            unidade_medida="sv",
            quantidade=Decimal("2"),
            valor_unitario=Decimal("50.00"),
        )

        response = self.client.post(
            reverse("orcamentos:item_duplicar", args=[self.orcamento.pk, item.pk])
        )

        self.assertRedirects(response, reverse("orcamentos:editar", args=[self.orcamento.pk]))
        itens = list(self.orcamento.itens.order_by("ordem", "id"))
        self.assertEqual(len(itens), 2)
        self.assertEqual(itens[0].ordem, 1)
        self.assertEqual(itens[1].ordem, 2)
        self.assertEqual(itens[1].nome, "Servico base")
        self.assertNotEqual(itens[0].pk, itens[1].pk)
        self.assertEqual(itens[0].codigo_item, "ORC-2026-0001-ITEM-001")
        self.assertEqual(itens[1].codigo_item, "ORC-2026-0001-ITEM-002")

    def test_redirect_de_acao_em_item_preserva_filtros_com_encoding_seguro(self):
        item = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            codigo_item="SERV-01",
            nome="Servico base",
            unidade_medida="sv",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("50.00"),
        )

        response = self.client.post(
            reverse("orcamentos:item_duplicar", args=[self.orcamento.pk, item.pk]),
            {
                "item_q": "serviço & teste",
                "item_categoria": "",
                "item_sort": "preco_maior",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("item_q=servi%C3%A7o+%26+teste", response.url)
        self.assertIn("item_sort=preco_maior", response.url)

    def test_item_pode_subir_e_descer_na_ordem(self):
        item_1 = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            codigo_item="ITEM-1",
            nome="Primeiro",
            unidade_medida="un",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("10.00"),
        )
        item_2 = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=2,
            codigo_item="ITEM-2",
            nome="Segundo",
            unidade_medida="un",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("20.00"),
        )

        response_subir = self.client.post(
            reverse("orcamentos:item_mover", args=[self.orcamento.pk, item_2.pk, "cima"])
        )
        self.assertRedirects(response_subir, reverse("orcamentos:editar", args=[self.orcamento.pk]))

        item_1.refresh_from_db()
        item_2.refresh_from_db()
        self.assertEqual(item_2.ordem, 1)
        self.assertEqual(item_1.ordem, 2)

        response_descer = self.client.post(
            reverse("orcamentos:item_mover", args=[self.orcamento.pk, item_2.pk, "baixo"])
        )
        self.assertRedirects(response_descer, reverse("orcamentos:editar", args=[self.orcamento.pk]))

        item_1.refresh_from_db()
        item_2.refresh_from_db()
        self.assertEqual(item_1.ordem, 1)
        self.assertEqual(item_2.ordem, 2)

    def test_item_excluido_normaliza_ordem_restante(self):
        item_1 = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            codigo_item="ITEM-1",
            nome="Primeiro",
            unidade_medida="un",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("10.00"),
        )
        item_2 = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=2,
            codigo_item="ITEM-2",
            nome="Segundo",
            unidade_medida="un",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("20.00"),
        )

        response = self.client.post(
            reverse("orcamentos:item_excluir", args=[self.orcamento.pk, item_1.pk])
        )

        self.assertRedirects(response, reverse("orcamentos:editar", args=[self.orcamento.pk]))
        item_2.refresh_from_db()
        self.assertEqual(item_2.ordem, 1)

    def test_preview_do_item_retorna_subtotal_calculado_no_backend(self):
        response = self.client.get(
            reverse("orcamentos:item_preview", args=[self.orcamento.pk]),
            {
                "nome": "Item preview",
                "unidade_medida": "un",
                "quantidade": "2,00",
                "valor_unitario": "R$ 100,00",
                "desconto_percentual": "10,00",
                "desconto_valor": "R$ 5,00",
                "acrescimo_valor": "R$ 20,00",
                "acrescimo_percentual": "0,00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "R$ 195,00")

    def test_edicao_de_item_e_carregada_para_o_modal(self):
        item = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            codigo_item="ITEM-1",
            nome="Primeiro",
            unidade_medida="un",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("10.00"),
        )

        response = self.client.get(
            reverse("orcamentos:item_editar", args=[self.orcamento.pk, item.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"modal_html": response.json()["modal_html"]},
        )
        self.assertIn("Cancelar", response.json()["modal_html"])
        self.assertIn("Salvar item", response.json()["modal_html"])

    def test_item_pode_ser_duplicado_para_edicao(self):
        item = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            codigo_item="ITEM-1",
            nome="Primeiro",
            unidade_medida="un",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("10.00"),
        )

        response = self.client.post(
            reverse("orcamentos:item_duplicar_editar", args=[self.orcamento.pk, item.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("?item_edit=", response.url)
        self.assertEqual(ItemOrcamento.objects.count(), 2)

    def test_orcamento_inativo_nao_exibe_acoes_de_status(self):
        self.orcamento.ativo = False
        self.orcamento.save(update_fields=["ativo", "atualizado_em"])

        response = self.client.get(reverse("orcamentos:lista"), {"ativo": "inativos"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inativo")
        self.assertNotContains(response, "title=\"Aprovar\"")
        self.assertNotContains(response, "title=\"Enviar\"")

    def test_orcamento_em_rascunho_exibe_fluxo_inicial_de_status(self):
        response = self.client.get(reverse("orcamentos:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'title="Enviar"')
        self.assertContains(response, 'title="Cancelar"')
        self.assertNotContains(response, 'title="Rascunho"')
        self.assertNotContains(response, 'title="Aprovar"')
        self.assertNotContains(response, 'title="Rejeitar"')

    def test_orcamento_aprovado_nao_exibe_retorno_para_rascunho_para_nao_admin(self):
        self.orcamento.status = "aprovado"
        self.orcamento.save(update_fields=["status", "atualizado_em"])

        response = self.client.get(reverse("orcamentos:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'title="Rascunho"')
        self.assertNotContains(response, 'title="Aprovar"')
        self.assertNotContains(response, 'title="Rejeitar"')
        self.assertNotContains(response, 'title="Cancelar"')

    def test_admin_exibe_retorno_para_rascunho_em_orcamento_aprovado(self):
        admin = get_user_model().objects.create_user(
            username="admin_lista_orcamento",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(admin)
        self.orcamento.status = "aprovado"
        self.orcamento.save(update_fields=["status", "atualizado_em"])

        response = self.client.get(reverse("orcamentos:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'title="Rascunho"')

    def test_duplicar_orcamento_cria_novo_rascunho_com_itens(self):
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            nome="Item duplicado",
            descricao="Descricao",
            unidade_medida="un",
            quantidade=Decimal("2.00"),
            valor_unitario=Decimal("15.00"),
        )

        response = self.client.post(reverse("orcamentos:duplicar", args=[self.orcamento.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Orcamento.objects.count(), 2)
        novo_orcamento = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        self.assertEqual(novo_orcamento.status, "rascunho")
        self.assertEqual(novo_orcamento.itens.count(), 1)
        self.assertNotEqual(novo_orcamento.numero, self.orcamento.numero)

    def test_orcamento_exibe_cor_da_categoria_do_item(self):
        categoria = CategoriaItem.objects.create(nome="Eletrica", cor="#0F766E")
        item_catalogo = ItemCatalogo.objects.create(
            codigo="ELE-01",
            nome="Ponto eletrico",
            categoria=categoria,
            unidade_medida="sv",
            valor_unitario_padrao=Decimal("80.00"),
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            item_catalogo=item_catalogo,
            ordem=1,
            nome="Ponto eletrico",
            unidade_medida="sv",
            quantidade=Decimal("1.00"),
            valor_unitario=Decimal("80.00"),
        )

        response = self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Eletrica")
        self.assertContains(response, "#0F766E")

    def test_orcamento_exibe_subtotais_por_categoria(self):
        categoria = CategoriaItem.objects.create(nome="Eletrica", cor="#0F766E")
        item_catalogo = ItemCatalogo.objects.create(
            codigo="ELE-01",
            nome="Ponto eletrico",
            categoria=categoria,
            unidade_medida="sv",
            valor_unitario_padrao=Decimal("80.00"),
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            item_catalogo=item_catalogo,
            ordem=1,
            nome="Ponto eletrico",
            unidade_medida="sv",
            quantidade=Decimal("2.00"),
            valor_unitario=Decimal("80.00"),
        )

        response = self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subtotal da categoria")
        self.assertContains(response, "Eletrica")
        self.assertContains(response, "R$ 160,00")

    def test_item_criar_via_ajax_retorna_fragments_sem_reload(self):
        response = self.client.post(
            reverse("orcamentos:item_criar", args=[self.orcamento.pk]),
            {
                "ordem": 1,
                "codigo_item": "AJX-1",
                "nome": "Item ajax",
                "descricao": "",
                "unidade_medida": "un",
                "quantidade": "2,00",
                "valor_unitario": "R$ 15,00",
                "desconto_valor": "R$ 0,00",
                "desconto_percentual": "0,00",
                "acrescimo_valor": "R$ 0,00",
                "acrescimo_percentual": "0,00",
                "observacoes": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("itens_html", data)
        self.assertIn("totais_html", data)
        self.assertIn("novo_item_html", data)
        self.assertIn("Item &#x27;Item ajax&#x27; adicionado.", data["flash_html"])

    def test_orcamento_aceita_campos_monetarios_formatados_em_pt_br(self):
        response = self.client.post(
            reverse("orcamentos:editar", args=[self.orcamento.pk]),
            {
                "numero": self.orcamento.numero,
                "cliente": self.cliente.pk,
                "titulo": "Titulo com valores localizados",
                "descricao_inicial": "",
                "observacoes_gerais": "",
                "status": self.orcamento.status,
                "data_emissao": self.orcamento.data_emissao.isoformat(),
                "validade_em": "",
                "desconto_global_valor": "R$ 1.500,50",
                "desconto_global_percentual": "5,50",
                "acrescimo_global_valor": "R$ 250,25",
                "acrescimo_global_percentual": "1,25",
                "mostrar_ajustes_no_relatorio": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.desconto_global_valor, Decimal("1500.50"))
        self.assertEqual(self.orcamento.desconto_global_percentual, Decimal("5.50"))
        self.assertEqual(self.orcamento.acrescimo_global_valor, Decimal("250.25"))
        self.assertEqual(self.orcamento.acrescimo_global_percentual, Decimal("1.25"))

    def test_lista_de_orcamentos_renderiza_total_em_padrao_brasileiro(self):
        self.orcamento.total_final = Decimal("15000.00")
        self.orcamento.save(update_fields=["total_final"])

        response = self.client.get(reverse("orcamentos:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "R$ 15.000,00")

    def test_lista_de_orcamentos_filtra_por_status(self):
        Orcamento.objects.create(
            numero="ORC-2026-0002",
            cliente=self.cliente,
            titulo="Aprovado",
            status="aprovado",
            data_emissao=date(2026, 4, 9),
            criado_por=self.user,
            atualizado_por=self.user,
        )

        response = self.client.get(reverse("orcamentos:lista"), {"status": "aprovado"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aprovado")
        self.assertNotContains(response, "Orcamento teste")

    def test_lista_de_orcamentos_filtra_por_ativo(self):
        Orcamento.objects.create(
            numero="ORC-2026-0002",
            cliente=self.cliente,
            titulo="Inativo",
            ativo=False,
            data_emissao=date(2026, 4, 9),
            criado_por=self.user,
            atualizado_por=self.user,
        )

        response = self.client.get(reverse("orcamentos:lista"), {"ativo": "ativos"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Orcamento teste")
        orcamentos = list(response.context["orcamentos"])
        self.assertEqual(len(orcamentos), 1)
        self.assertEqual(orcamentos[0].titulo, "Orcamento teste")

    def test_lista_de_orcamentos_e_paginada(self):
        for indice in range(13):
            Orcamento.objects.create(
                numero=f"ORC-2026-{indice + 10:04d}",
                cliente=self.cliente,
                titulo=f"Extra {indice:02d}",
                data_emissao=date(2026, 4, 9),
                criado_por=self.user,
                atualizado_por=self.user,
            )

        response = self.client.get(reverse("orcamentos:lista"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_previous())
        self.assertContains(response, "Extra 00")

    def test_tela_de_orcamento_renderiza_hooks_de_rascunho_e_alerta(self):
        response = self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-unsaved-warning="1"')
        self.assertContains(response, f'data-draft-key="orcamento:{self.orcamento.pk}:principal"')

    def test_resposta_ajax_de_item_mantem_hooks_de_rascunho(self):
        response = self.client.post(
            reverse("orcamentos:item_criar", args=[self.orcamento.pk]),
            {
                "ordem": 1,
                "codigo_item": "",
                "nome": "",
                "descricao": "",
                "unidade_medida": "",
                "quantidade": "",
                "valor_unitario": "",
                "item_q": "busca",
                "item_sort": "nome",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('data-unsaved-warning="1"', data["novo_item_html"])
        self.assertIn(f'data-draft-key="orcamento:{self.orcamento.pk}:item:novo"', data["novo_item_html"])

    def test_edicao_nao_permite_alterar_numero_existente(self):
        response = self.client.post(
            reverse("orcamentos:editar", args=[self.orcamento.pk]),
            {
                "numero": "ORC-2099-9999",
                "cliente": self.cliente.pk,
                "titulo": "Titulo mantido",
                "descricao_inicial": "",
                "observacoes_gerais": "",
                "status": self.orcamento.status,
                "data_emissao": self.orcamento.data_emissao.isoformat(),
                "validade_em": "",
                "desconto_global_valor": "0.00",
                "desconto_global_percentual": "0.00",
                "acrescimo_global_valor": "0.00",
                "acrescimo_global_percentual": "0.00",
                "mostrar_ajustes_no_relatorio": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.numero, "ORC-2026-0001")

    def test_orcamento_pode_ser_inativado_e_reativado(self):
        response = self.client.post(reverse("orcamentos:excluir", args=[self.orcamento.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Orçamento inativado com sucesso.")
        self.orcamento.refresh_from_db()
        self.assertFalse(self.orcamento.ativo)

        response = self.client.post(reverse("orcamentos:excluir", args=[self.orcamento.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Orçamento reativado com sucesso.")
        self.orcamento.refresh_from_db()
        self.assertTrue(self.orcamento.ativo)


class OrcamentoDomainTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dominio",
            password="senha-forte-123",
        )
        self.cliente = Cliente.objects.create(nome_razao_social="Cliente Dominio")
        self.orcamento = Orcamento.objects.create(
            numero="ORC-DOM-0001",
            cliente=self.cliente,
            titulo="Dominio",
            data_emissao=date(2026, 4, 9),
            criado_por=self.user,
            atualizado_por=self.user,
        )

    def test_item_calcula_subtotal_com_percentual_e_valor(self):
        item = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            nome="Servico",
            unidade_medida="un",
            quantidade=Decimal("2"),
            valor_unitario=Decimal("100.00"),
            desconto_valor=Decimal("5.00"),
            desconto_percentual=Decimal("10.00"),
            acrescimo_valor=Decimal("20.00"),
            acrescimo_percentual=Decimal("0.00"),
        )

        self.assertEqual(item.subtotal, Decimal("195.00"))

    def test_item_impede_desconto_maior_que_valor_base(self):
        item = ItemOrcamento(
            orcamento=self.orcamento,
            ordem=1,
            nome="Servico",
            unidade_medida="un",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("100.00"),
            desconto_valor=Decimal("101.00"),
        )

        with self.assertRaisesMessage(ValidationError, "O desconto total do item não pode ser maior que o valor base do item."):
            item.full_clean()

    def test_total_final_do_orcamento_nunca_fica_negativo(self):
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            nome="Servico",
            unidade_medida="un",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("50.00"),
        )
        self.orcamento.desconto_global_valor = Decimal("100.00")
        self.orcamento.recalcular_totais()

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.total_final, Decimal("0.00"))

    def test_signal_recalcula_totais_ao_salvar_e_excluir_item(self):
        item = ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            nome="Servico",
            unidade_medida="un",
            quantidade=Decimal("2"),
            valor_unitario=Decimal("30.00"),
        )
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.subtotal_itens, Decimal("60.00"))
        self.assertEqual(self.orcamento.total_final, Decimal("60.00"))

        item.delete()
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.subtotal_itens, Decimal("0.00"))
        self.assertEqual(self.orcamento.total_final, Decimal("0.00"))


class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dashboard_user",
            password="senha-forte-123",
        )
        self.client.force_login(self.user)
        cliente = Cliente.objects.create(nome_razao_social="Cliente Dashboard")
        Orcamento.objects.create(
            numero="ORC-ATIVO-0001",
            cliente=cliente,
            titulo="Ativo",
            ativo=True,
            data_emissao=date(2026, 4, 9),
            criado_por=self.user,
            atualizado_por=self.user,
        )
        Orcamento.objects.create(
            numero="ORC-INATIVO-0001",
            cliente=cliente,
            titulo="Inativo",
            ativo=False,
            data_emissao=date(2026, 4, 9),
            criado_por=self.user,
            atualizado_por=self.user,
        )

    def test_dashboard_nao_lista_orcamentos_inativos(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        ultimos = list(response.context["ultimos_orcamentos"])
        self.assertEqual(len(ultimos), 1)
        self.assertEqual(ultimos[0].titulo, "Ativo")
