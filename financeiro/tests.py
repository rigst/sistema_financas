from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CategoriaFinanceira, CartaoCredito, Conta, FaturaCartao, LancamentoCartao, RecorrenciaFinanceira, Transacao


class FinanceiroModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="fin_user", password="senha-forte-123")
        self.conta_origem = Conta.objects.create(nome="Conta origem", saldo_inicial=Decimal("100.00"))
        self.conta_destino = Conta.objects.create(nome="Conta destino", saldo_inicial=Decimal("20.00"))
        self.receita = CategoriaFinanceira.objects.create(nome="Salário", tipo="receita")
        self.despesa = CategoriaFinanceira.objects.create(nome="Mercado", tipo="despesa")

    def test_saldo_considera_receitas_despesas_e_transferencias_pagas(self):
        hoje = timezone.localdate()
        Transacao.objects.create(tipo="receita", descricao="Receita", valor=Decimal("500.00"), data_competencia=hoje, data_pagamento=hoje, status="pago", conta=self.conta_origem, categoria=self.receita, criado_por=self.user)
        Transacao.objects.create(tipo="despesa", descricao="Despesa", valor=Decimal("80.00"), data_competencia=hoje, data_pagamento=hoje, status="pago", conta=self.conta_origem, categoria=self.despesa, criado_por=self.user)
        Transacao.objects.create(tipo="transferencia", descricao="Reserva", valor=Decimal("120.00"), data_competencia=hoje, data_pagamento=hoje, status="pago", conta=self.conta_origem, conta_destino=self.conta_destino, criado_por=self.user)
        Transacao.objects.create(tipo="despesa", descricao="Pendente", valor=Decimal("30.00"), data_competencia=hoje, status="pendente", conta=self.conta_origem, categoria=self.despesa, criado_por=self.user)

        self.assertEqual(self.conta_origem.saldo_atual(), Decimal("400.00"))
        self.assertEqual(self.conta_destino.saldo_atual(), Decimal("140.00"))

    def test_transacao_rejeita_categoria_de_tipo_incompativel(self):
        transacao = Transacao(
            tipo="despesa",
            descricao="Categoria errada",
            valor=Decimal("10.00"),
            data_competencia=timezone.localdate(),
            data_pagamento=timezone.localdate(),
            status="pago",
            conta=self.conta_origem,
            categoria=self.receita,
            criado_por=self.user,
        )

        with self.assertRaises(ValidationError):
            transacao.full_clean()


class FinanceiroViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="fin_view", password="senha-forte-123")
        self.client.force_login(self.user)

    def test_fluxo_basico_de_conta_categoria_e_transacao(self):
        response_conta = self.client.post(
            reverse("financeiro:conta_criar"),
            {
                "nome": "Nubank",
                "tipo": "corrente",
                "instituicao": "Nubank",
                "saldo_inicial": "100,00",
                "data_saldo_inicial": "2026-04-01",
                "cor": "#2563EB",
                "ativa": "True",
            },
        )
        self.assertEqual(response_conta.status_code, 302)
        conta = Conta.objects.get(nome="Nubank")

        response_categoria = self.client.post(
            reverse("financeiro:categoria_criar"),
            {
                "nome": "Salário",
                "tipo": "receita",
                "categoria_pai": "",
                "cor": "#16A34A",
                "icone": "",
                "ativa": "True",
            },
        )
        self.assertEqual(response_categoria.status_code, 302)
        categoria = CategoriaFinanceira.objects.get(nome="Salário")

        response_transacao = self.client.post(
            reverse("financeiro:transacao_criar"),
            {
                "tipo": "receita",
                "descricao": "Salário abril",
                "valor": "2500,00",
                "data_competencia": "2026-04-16",
                "data_pagamento": "2026-04-16",
                "status": "pago",
                "conta": str(conta.pk),
                "conta_destino": "",
                "categoria": str(categoria.pk),
                "observacoes": "",
            },
        )
        self.assertEqual(response_transacao.status_code, 302)
        self.assertEqual(conta.saldo_atual(), Decimal("2600.00"))


class CartaoFaturaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="card_user", password="senha-forte-123")
        self.client.force_login(self.user)
        self.conta = Conta.objects.create(nome="Conta pagamento", saldo_inicial=Decimal("1000.00"))
        self.categoria = CategoriaFinanceira.objects.create(nome="Cartão de crédito", tipo="despesa")

    def test_compra_parcelada_cria_faturas_e_pagamento_baixa_conta(self):
        response_cartao = self.client.post(
            reverse("financeiro:cartao_criar"),
            {
                "nome": "Nubank Crédito",
                "bandeira": "mastercard",
                "limite": "5000,00",
                "dia_fechamento": "5",
                "dia_vencimento": "12",
                "conta_pagamento": str(self.conta.pk),
                "cor": "#111827",
                "ativo": "True",
            },
        )
        self.assertEqual(response_cartao.status_code, 302)
        cartao = CartaoCredito.objects.get(nome="Nubank Crédito")

        response_compra = self.client.post(
            reverse("financeiro:compra_cartao_criar"),
            {
                "cartao": str(cartao.pk),
                "categoria": str(self.categoria.pk),
                "descricao": "Notebook",
                "valor_total": "1200,00",
                "data_compra": "2026-04-16",
                "parcelas": "3",
                "mes_primeira_fatura": "5",
                "ano_primeira_fatura": "2026",
                "observacoes": "",
            },
        )
        self.assertEqual(response_compra.status_code, 302)
        self.assertEqual(FaturaCartao.objects.filter(cartao=cartao).count(), 3)
        self.assertEqual(LancamentoCartao.objects.filter(cartao=cartao).count(), 3)
        primeira_fatura = FaturaCartao.objects.get(cartao=cartao, mes=5, ano=2026)
        self.assertEqual(primeira_fatura.valor_total, Decimal("400.00"))
        self.assertEqual(self.conta.saldo_atual(), Decimal("1000.00"))

        response_pagamento = self.client.post(
            reverse("financeiro:fatura_pagar", args=[primeira_fatura.pk]),
            {
                "conta_pagamento": str(self.conta.pk),
                "categoria_pagamento": str(self.categoria.pk),
                "data_pagamento": "2026-05-12",
            },
        )
        self.assertEqual(response_pagamento.status_code, 302)
        primeira_fatura.refresh_from_db()
        self.assertEqual(primeira_fatura.status, "paga")
        self.assertIsNotNone(primeira_fatura.transacao_pagamento)
        self.assertEqual(self.conta.saldo_atual(), Decimal("600.00"))


class FinanceiroCompletoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="full_user", password="senha-forte-123")
        self.client.force_login(self.user)
        self.conta = Conta.objects.create(nome="Conta completa", saldo_inicial=Decimal("1000.00"))
        self.receita = CategoriaFinanceira.objects.create(nome="Receita completa", tipo="receita")
        self.despesa = CategoriaFinanceira.objects.create(nome="Despesa completa", tipo="despesa")
        self.cartao = CartaoCredito.objects.create(nome="Cartão completo", bandeira="visa", limite=Decimal("2000.00"), dia_fechamento=5, dia_vencimento=10, conta_pagamento=self.conta)

    def test_relatorio_planejamento_meta_e_recorrencia_respondem(self):
        Transacao.objects.create(tipo="despesa", descricao="Mercado", valor=Decimal("120.00"), data_competencia="2026-04-16", data_pagamento="2026-04-16", status="pago", conta=self.conta, categoria=self.despesa, criado_por=self.user)
        response_relatorio = self.client.get(reverse("financeiro:relatorio_fluxo_caixa"), {"mes": 4, "ano": 2026})
        self.assertEqual(response_relatorio.status_code, 200)
        self.assertContains(response_relatorio, "R$ 120,00")

        response_planejamento = self.client.post(reverse("financeiro:planejamento_criar"), {"mes": "4", "ano": "2026", "categoria": str(self.despesa.pk), "valor_planejado": "500,00"})
        self.assertEqual(response_planejamento.status_code, 302)
        self.assertContains(self.client.get(reverse("financeiro:planejamento_lista"), {"mes": 4, "ano": 2026}), "R$ 380,00")

        response_meta = self.client.post(reverse("financeiro:meta_criar"), {"nome": "Reserva", "valor_alvo": "1000,00", "valor_atual_manual": "250,00", "data_inicio": "2026-04-01", "data_limite": "2026-12-31", "conta_vinculada": "", "status": "ativa", "cor": "#16A34A", "observacoes": ""})
        self.assertEqual(response_meta.status_code, 302)
        self.assertContains(self.client.get(reverse("financeiro:meta_lista")), "Reserva")

        response_rec = self.client.post(reverse("financeiro:recorrencia_criar"), {"tipo": "receita", "descricao": "Salário", "valor": "3000,00", "categoria": str(self.receita.pk), "conta": str(self.conta.pk), "frequencia": "mensal", "dia_vencimento": "5", "data_inicio": "2026-04-05", "data_fim": "", "ativa": "True", "observacoes": ""})
        self.assertEqual(response_rec.status_code, 302)
        rec = RecorrenciaFinanceira.objects.get(descricao="Salário")
        response_gerar = self.client.post(reverse("financeiro:recorrencia_gerar", args=[rec.pk]))
        self.assertEqual(response_gerar.status_code, 302)
        self.assertEqual(Transacao.objects.filter(descricao="Salário").count(), 12)

    def test_nao_permite_alterar_fatura_paga_ou_lancar_em_fatura_paga(self):
        fatura = FaturaCartao.objects.create(cartao=self.cartao, mes=4, ano=2026, conta_pagamento=self.conta)
        LancamentoCartao.objects.create(fatura=fatura, cartao=self.cartao, categoria=self.despesa, descricao="Compra", valor=Decimal("100.00"), data_compra="2026-04-01", empresa=fatura.empresa, criado_por=self.user)
        fatura.pagar(conta=self.conta, categoria=self.despesa, data_pagamento=timezone.localdate(), usuario=self.user)

        response = self.client.post(reverse("financeiro:compra_cartao_criar"), {"cartao": str(self.cartao.pk), "categoria": str(self.despesa.pk), "descricao": "Outra compra", "valor_total": "50,00", "data_compra": "2026-04-02", "parcelas": "1", "mes_primeira_fatura": "4", "ano_primeira_fatura": "2026", "observacoes": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "não aceita novos lançamentos")
        self.assertEqual(LancamentoCartao.objects.filter(fatura=fatura).count(), 1)
