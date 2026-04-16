from io import BytesIO

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from decimal import Decimal

from catalogo.models import CategoriaItem, ItemCatalogo
from clientes.models import Cliente
from orcamentos.models import ItemOrcamento, Orcamento
from .models import ConfiguracaoEmpresa


class RelatoriosPermissaoTests(TestCase):
    def gerar_logo_teste(self):
        buffer = BytesIO()
        Image.new("RGB", (180, 60), color=(80, 140, 220)).save(buffer, format="PNG")
        return SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")

    def test_orcamentista_nao_pode_criar_configuracao_empresa(self):
        user = get_user_model().objects.create_user(
            username="orcamentista",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("relatorios:configuracao_criar"))

        self.assertEqual(response.status_code, 403)

    def test_visualizador_pode_visualizar_configuracao(self):
        user = get_user_model().objects.create_user(
            username="visualizador_empresa",
            password="senha-forte-123",
            perfil="visualizador",
        )
        configuracao = ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa Visivel")
        self.client.force_login(user)

        response = self.client.get(reverse("relatorios:configuracao_visualizar", args=[configuracao.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Empresa Visivel")

    def test_visualizador_nao_pode_alterar_opcoes_do_relatorio(self):
        user = get_user_model().objects.create_user(
            username="visualizador_relatorio",
            password="senha-forte-123",
            perfil="visualizador",
        )
        cliente = Cliente.objects.create(nome_razao_social="Cliente Permissao")
        orcamento = Orcamento.objects.create(
            numero="ORC-REL-0009",
            cliente=cliente,
            titulo="Teste permissao",
            status="rascunho",
            data_emissao="2026-04-09",
            criado_por=user,
            atualizado_por=user,
        )
        self.client.force_login(user)

        response = self.client.post(reverse("relatorios:orcamento_central", args=[orcamento.pk]), {"mostrar_ajustes_no_relatorio": "on"})

        self.assertEqual(response.status_code, 403)

    def test_logo_configuracao_exige_login(self):
        configuracao = ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa Visivel", logo=self.gerar_logo_teste())

        response = self.client.get(reverse("relatorios:configuracao_logo", args=[configuracao.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_logo_configuracao_so_e_acessivel_na_mesma_empresa(self):
        empresa_a = Group.objects.create(name="Empresa A")
        empresa_b = Group.objects.create(name="Empresa B")
        usuario_a = get_user_model().objects.create_user(
            username="usuario_logo_a",
            password="senha-forte-123",
            perfil="visualizador",
        )
        usuario_a.groups.set([empresa_a])
        usuario_b = get_user_model().objects.create_user(
            username="usuario_logo_b",
            password="senha-forte-123",
            perfil="visualizador",
        )
        usuario_b.groups.set([empresa_b])

        configuracao_a = ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa A",
            empresa=empresa_a,
            logo=self.gerar_logo_teste(),
        )
        configuracao_b = ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa B",
            empresa=empresa_b,
            logo=self.gerar_logo_teste(),
        )

        self.client.force_login(usuario_a)
        response_propria = self.client.get(reverse("relatorios:configuracao_logo", args=[configuracao_a.pk]))
        response_outra = self.client.get(reverse("relatorios:configuracao_logo", args=[configuracao_b.pk]))
        self.client.force_login(usuario_b)
        response_b = self.client.get(reverse("relatorios:configuracao_logo", args=[configuracao_b.pk]))

        self.assertEqual(response_propria.status_code, 200)
        self.assertEqual(response_propria["Content-Type"], "image/png")
        self.assertEqual(response_outra.status_code, 404)
        self.assertEqual(response_b.status_code, 200)


class RelatoriosExportacaoTests(TestCase):
    def gerar_logo_teste(self):
        buffer = BytesIO()
        Image.new("RGB", (180, 60), color=(80, 140, 220)).save(buffer, format="PNG")
        return SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="orcamentista_export",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(self.user)

        self.cliente = Cliente.objects.create(nome_razao_social="Cliente Exportacao")
        self.orcamento = Orcamento.objects.create(
            numero="ORC-REL-0001",
            cliente=self.cliente,
            titulo="Relatorio profissional",
            status="rascunho",
            data_emissao="2026-04-09",
            criado_por=self.user,
            atualizado_por=self.user,
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            codigo_item="REL-1",
            nome="Servico relatorio",
            unidade_medida="un",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("15000.00"),
        )
        self.orcamento.refresh_from_db()
        ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa Exemplo",
            logo=self.gerar_logo_teste(),
        )

    def test_central_de_relatorio_mostra_alerta_de_status(self):
        response = self.client.get(reverse("relatorios:orcamento_central", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Orçamento em rascunho")
        self.assertContains(response, "Logo da empresa")
        self.assertContains(
            response,
            reverse("relatorios:configuracao_logo", args=[ConfiguracaoEmpresa.objects.get().pk]),
        )
        self.assertContains(response, "R$ 15.000,00")

    def test_central_de_relatorio_atualiza_opcao_de_mostrar_ajustes(self):
        response = self.client.post(
            reverse("relatorios:orcamento_central", args=[self.orcamento.pk]),
            {"mostrar_ajustes_no_relatorio": "on"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.orcamento.refresh_from_db()
        self.assertTrue(self.orcamento.mostrar_ajustes_no_relatorio)
        self.assertContains(response, "Opções do relatório atualizadas.")

    def test_central_de_relatorio_exibe_opcoes_adicionais_e_exportacao_word(self):
        response = self.client.get(reverse("relatorios:orcamento_central", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mostrar descrição inicial")
        self.assertContains(response, "Mostrar informações financeiras")
        self.assertContains(response, reverse("relatorios:orcamento_memorial_word", args=[self.orcamento.pk]))
        self.assertContains(response, "Baixar Memorial em Word")

    def test_relatorios_respeitam_configuracao_vinculada_ao_orcamento(self):
        self.orcamento.configuracao_empresa = ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa Escolhida",
            cidade="Curitiba",
        )
        self.orcamento.save(update_fields=["configuracao_empresa", "atualizado_em"])
        ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa Mais Recente",
            cidade="Campinas",
        )

        response = self.client.get(reverse("relatorios:orcamento_central", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Empresa Escolhida")
        self.assertContains(response, "Curitiba")
        self.assertNotContains(response, "Empresa Mais Recente")

    def test_central_de_relatorio_atualiza_multiplas_opcoes(self):
        response = self.client.post(
            reverse("relatorios:orcamento_central", args=[self.orcamento.pk]),
            {
                "mostrar_ajustes_no_relatorio": "on",
                "mostrar_descricao_inicial_no_relatorio": "on",
                "mostrar_rodape_institucional_no_relatorio": "on",
                "mostrar_financeiro_no_memorial": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.orcamento.refresh_from_db()
        self.assertTrue(self.orcamento.mostrar_ajustes_no_relatorio)
        self.assertTrue(self.orcamento.mostrar_descricao_inicial_no_relatorio)
        self.assertFalse(self.orcamento.mostrar_observacoes_gerais_no_relatorio)
        self.assertTrue(self.orcamento.mostrar_rodape_institucional_no_relatorio)
        self.assertFalse(self.orcamento.mostrar_contatos_evento_no_memorial)
        self.assertTrue(self.orcamento.mostrar_financeiro_no_memorial)
        self.assertFalse(self.orcamento.mostrar_dados_contratuais_no_memorial)
        self.assertFalse(self.orcamento.mostrar_informacoes_complementares_no_memorial)
        self.assertContains(response, "Opções do relatório atualizadas.")

    def test_exportacao_excel_retorna_arquivo(self):
        categoria = CategoriaItem.objects.create(nome="Civil", cor="#2563EB")
        item_catalogo = ItemCatalogo.objects.create(
            codigo="CIV-EXCEL-01",
            nome="Servico civil",
            categoria=categoria,
            unidade_medida="sv",
            valor_unitario_padrao=Decimal("100.00"),
            descricao_padrao="Descricao do item no excel",
        )
        item = self.orcamento.itens.first()
        item.item_catalogo = item_catalogo
        item.descricao = "Descricao detalhada"
        item.save(update_fields=["item_catalogo", "descricao", "atualizado_em"])
        self.orcamento.descricao_inicial = "Introducao do PDF"
        self.orcamento.observacoes_gerais = "Observacoes do documento"
        self.orcamento.save(update_fields=["descricao_inicial", "observacoes_gerais", "atualizado_em"])
        configuracao = ConfiguracaoEmpresa.objects.get()
        configuracao.rodape_relatorio = "Rodape institucional"
        configuracao.save(update_fields=["rodape_relatorio", "atualizado_em"])

        response = self.client.get(reverse("relatorios:orcamento_excel", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.ms-excel")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(b"Or\xc3\xa7amento em rascunho", response.content)
        self.assertIn("Categoria".encode("utf-8"), response.content)
        self.assertIn("Civil".encode("utf-8"), response.content)
        self.assertIn("Descricao detalhada".encode("utf-8"), response.content)
        self.assertIn("Descrição inicial: Introducao do PDF".encode("utf-8"), response.content)
        self.assertIn("Observações gerais: Observacoes do documento".encode("utf-8"), response.content)
        self.assertIn("Rodapé institucional: Rodape institucional".encode("utf-8"), response.content)

    def test_exportacao_pdf_retorna_arquivo(self):
        response = self.client.get(reverse("relatorios:orcamento_pdf", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Subtype /Image", response.content)

    def test_exportacao_memorial_descritivo_retorna_arquivo(self):
        categoria = CategoriaItem.objects.create(nome="Civil", cor="#2563EB")
        item_catalogo = ItemCatalogo.objects.create(
            codigo="CIV-01",
            nome="Servico civil",
            categoria=categoria,
            unidade_medida="sv",
            valor_unitario_padrao=Decimal("100.00"),
        )
        item = self.orcamento.itens.first()
        item.item_catalogo = item_catalogo
        item.descricao = "Descricao longa do servico"
        item.save()
        self.orcamento.evento_nome = "Expodireto 2026"
        self.orcamento.evento_local = "Nao-Me-Toque/RS"
        self.orcamento.evento_contato = "Mariana"
        self.orcamento.condicoes_pagamento = "30% na aprovacao"
        self.orcamento.contrato_razao_social = "Cliente Exportacao LTDA"
        self.orcamento.save(update_fields=["evento_nome", "evento_local", "evento_contato", "condicoes_pagamento", "contrato_razao_social"])
        configuracao = ConfiguracaoEmpresa.objects.get()
        configuracao.dados_bancarios = "Banco 001 Ag 1234 Cc 99999-9"
        configuracao.chave_pix = "pix@empresa.com"
        configuracao.assinatura_nome = "Diretoria Comercial"
        configuracao.texto_institucional_memorial = "Documento emitido para fins comerciais."
        configuracao.save()

        response = self.client.get(reverse("relatorios:orcamento_memorial_pdf", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-1.4"))
        self.assertIn("Memorial Descritivo".encode("utf-8"), response.content)
        self.assertIn("CIVIL".encode("utf-8"), response.content)
        self.assertIn("Descricao longa do servico".encode("utf-8"), response.content)
        self.assertIn("Expodireto 2026".encode("utf-8"), response.content)
        self.assertIn("30% na aprovacao".encode("utf-8"), response.content)
        self.assertIn("Cliente Exportacao LTDA".encode("utf-8"), response.content)
        self.assertIn("pix@empresa.com".encode("utf-8"), response.content)

    def test_exportacao_memorial_word_retorna_arquivo(self):
        self.orcamento.evento_contato = "Mariana"
        self.orcamento.condicoes_pagamento = "30% na aprovacao"
        self.orcamento.contrato_razao_social = "Cliente Exportacao LTDA"
        self.orcamento.observacoes_gerais = "Observacoes para Word"
        self.orcamento.save(
            update_fields=[
                "evento_contato",
                "condicoes_pagamento",
                "contrato_razao_social",
                "observacoes_gerais",
                "atualizado_em",
            ]
        )
        configuracao = ConfiguracaoEmpresa.objects.get()
        configuracao.chave_pix = "pix@empresa.com"
        configuracao.save(update_fields=["chave_pix", "atualizado_em"])

        response = self.client.get(reverse("relatorios:orcamento_memorial_word", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/rtf")
        self.assertIn('.rtf"', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"{\\rtf1"))
        self.assertIn("Relatorio profissional".encode("utf-8"), response.content)
        self.assertIn("Mariana".encode("utf-8"), response.content)
        self.assertIn("Cliente Exportacao LTDA".encode("utf-8"), response.content)
        self.assertIn("pix@empresa.com".encode("utf-8"), response.content)

    def test_exportacao_memorial_word_omite_blocos_desmarcados(self):
        self.orcamento.evento_contato = "Mariana"
        self.orcamento.condicoes_pagamento = "30% na aprovacao"
        self.orcamento.contrato_razao_social = "Cliente Exportacao LTDA"
        self.orcamento.observacoes_gerais = "Observacoes ocultas"
        self.orcamento.mostrar_contatos_evento_no_memorial = False
        self.orcamento.mostrar_financeiro_no_memorial = False
        self.orcamento.mostrar_dados_contratuais_no_memorial = False
        self.orcamento.mostrar_observacoes_gerais_no_relatorio = False
        self.orcamento.save(
            update_fields=[
                "evento_contato",
                "condicoes_pagamento",
                "contrato_razao_social",
                "observacoes_gerais",
                "mostrar_contatos_evento_no_memorial",
                "mostrar_financeiro_no_memorial",
                "mostrar_dados_contratuais_no_memorial",
                "mostrar_observacoes_gerais_no_relatorio",
                "atualizado_em",
            ]
        )

        response = self.client.get(reverse("relatorios:orcamento_memorial_word", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Mariana".encode("utf-8"), response.content)
        self.assertNotIn("Cliente Exportacao LTDA".encode("utf-8"), response.content)
        self.assertNotIn("30% na aprovacao".encode("utf-8"), response.content)
        self.assertNotIn("Observacoes ocultas".encode("utf-8"), response.content)


class RelatoriosValidacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_relatorios",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_configuracao_empresa_invalida_exibe_erros(self):
        response = self.client.post(
            reverse("relatorios:configuracao_criar"),
            {
                "nome_empresa": "",
                "cpf_cnpj": "123",
                "telefone": "9999",
                "cep": "123",
                "estado": "XX",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe o nome da empresa.")
        self.assertContains(response, "Informe um CPF com 11 dígitos ou um CNPJ com 14 dígitos.")
        self.assertContains(response, "Telefone deve ter 10 ou 11 dígitos, incluindo DDD.")
        self.assertContains(response, "CEP deve ter 8 dígitos.")
        self.assertContains(response, "Informe uma UF válida com duas letras.")

    def test_configuracao_empresa_aceita_campos_com_mascara(self):
        response = self.client.post(
            reverse("relatorios:configuracao_criar"),
            {
                "nome_empresa": "Empresa Formatada",
                "cpf_cnpj": "12.345.678/0001-90",
                "telefone": "(11) 4002-8922",
                "cep": "01310-100",
                "estado": "SP",
                "dados_bancarios": "Banco Exemplo",
                "chave_pix": "financeiro@empresa.com",
                "validade_padrao_proposta": "15 dias",
                "assinatura_nome": "Diretoria",
                "assinatura_cargo": "Comercial",
                "assinatura_contato": "(11) 4002-8922",
                "texto_institucional_memorial": "Texto padrao",
            },
        )

        self.assertEqual(response.status_code, 302)
        configuracao = ConfiguracaoEmpresa.objects.get(nome_empresa="Empresa Formatada")
        self.assertEqual(configuracao.cpf_cnpj, "12.345.678/0001-90")
        self.assertEqual(configuracao.telefone, "(11) 4002-8922")
        self.assertEqual(configuracao.cep, "01310-100")
        self.assertEqual(configuracao.chave_pix, "financeiro@empresa.com")
        self.assertEqual(configuracao.validade_padrao_proposta, "15 dias")


class RelatoriosListaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_lista_rel",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)
        ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa B", cidade="Rio de Janeiro")
        ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa A", cidade="Campinas")

    def test_lista_filtra_por_nome(self):
        response = self.client.get(reverse("relatorios:configuracao_lista"), {"q": "Empresa B"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Empresa B")
        self.assertNotContains(response, "Empresa A")

    def test_lista_ordena_por_nome(self):
        response = self.client.get(reverse("relatorios:configuracao_lista"), {"sort": "nome"})

        self.assertEqual(response.status_code, 200)
        configuracoes = list(response.context["configuracoes"])
        self.assertEqual(configuracoes[0].nome_empresa, "Empresa A")

    def test_lista_exibe_botao_principal_com_texto(self):
        response = self.client.get(reverse("relatorios:configuracao_lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nova configuração")

    def test_lista_de_configuracoes_e_paginada(self):
        for indice in range(11):
            ConfiguracaoEmpresa.objects.create(nome_empresa=f"Empresa Extra {indice:02d}")

        response = self.client.get(reverse("relatorios:configuracao_lista"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_previous())
        self.assertContains(response, "Empresa Extra 00")


class RelatoriosInativacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_toggle_empresa",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_configuracao_pode_ser_inativada(self):
        configuracao = ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa Toggle")

        response = self.client.post(reverse("relatorios:configuracao_excluir", args=[configuracao.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Configuração inativada com sucesso.")
        configuracao.refresh_from_db()
        self.assertFalse(configuracao.ativo)


class RelatoriosAtualizacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_edita_empresa",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_formulario_de_edicao_exibe_aviso_sobre_orcamentos_nao_enviados(self):
        configuracao = ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa Base")

        response = self.client.get(reverse("relatorios:configuracao_editar", args=[configuracao.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "orçamentos ainda não enviados")
        self.assertContains(response, ">Voltar<", html=False)
        self.assertContains(response, "Salvar empresa")

    def test_edicao_de_configuracao_exibe_mensagem_de_propagacao(self):
        configuracao = ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa Base")

        response = self.client.post(
            reverse("relatorios:configuracao_editar", args=[configuracao.pk]),
            {
                "nome_empresa": "Empresa Atualizada",
                "nome_fantasia": configuracao.nome_fantasia,
                "cpf_cnpj": configuracao.cpf_cnpj,
                "email": configuracao.email,
                "telefone": configuracao.telefone,
                "site": configuracao.site,
                "cep": configuracao.cep,
                "logradouro": configuracao.logradouro,
                "numero": configuracao.numero,
                "complemento": configuracao.complemento,
                "bairro": configuracao.bairro,
                "cidade": configuracao.cidade,
                "estado": configuracao.estado,
                "rodape_relatorio": configuracao.rodape_relatorio,
                "ativo": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Os relatórios e os orçamentos ainda não enviados passam a usar essas informações.",
        )
