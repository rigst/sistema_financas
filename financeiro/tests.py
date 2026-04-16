from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CategoriaFinanceira, Conta, Transacao


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
