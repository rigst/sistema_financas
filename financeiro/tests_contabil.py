"""Validação e saldo dos modelos contábeis: conta, categoria, cartão e recorrência.

Estes caminhos existiam sem teste. Eram as regras de `clean()` — as que impedem
uma transferência sem conta destino, um lançamento de cartão numa fatura de
outro cartão, uma categoria filha de tipo diferente do pai — e o `save()` que
as invoca. Regra de validação sem teste é uma regra que já foi apagada uma vez
sem ninguém perceber.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.testing import SENHA_TESTE

from .models import (
    CartaoCredito,
    CategoriaFinanceira,
    Conta,
    FaturaCartao,
    LancamentoCartao,
    MetaFinanceira,
    RecorrenciaFinanceira,
    Transacao,
)

Usuario = get_user_model()


class CategoriaFinanceiraCleanTests(TestCase):
    def setUp(self):
        self.despesas = CategoriaFinanceira.objects.create(nome="Casa", tipo="despesa")

    def test_categoria_nao_pode_ser_pai_dela_mesma(self):
        self.despesas.categoria_pai = self.despesas

        with self.assertRaises(ValidationError) as erro:
            self.despesas.clean()

        self.assertIn("categoria_pai", erro.exception.message_dict)

    def test_categoria_pai_precisa_ser_do_mesmo_tipo(self):
        receitas = CategoriaFinanceira.objects.create(nome="Salário", tipo="receita")
        filha = CategoriaFinanceira(nome="Aluguel", tipo="despesa", categoria_pai=receitas)

        with self.assertRaises(ValidationError) as erro:
            filha.clean()

        self.assertIn("mesmo tipo", str(erro.exception))

    def test_categoria_pai_do_mesmo_tipo_e_aceita(self):
        filha = CategoriaFinanceira(nome="Aluguel", tipo="despesa", categoria_pai=self.despesas)

        filha.clean()  # não levanta


class TransacaoCleanTests(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(username="contabil", password=SENHA_TESTE)
        self.conta = Conta.objects.create(nome="Corrente", saldo_inicial=Decimal("100.00"))
        self.outra = Conta.objects.create(nome="Poupança", saldo_inicial=Decimal("0.00"))
        self.categoria_despesa = CategoriaFinanceira.objects.create(nome="Mercado", tipo="despesa")

    def _transacao(self, **campos):
        padrao = {
            "tipo": "despesa",
            "descricao": "Compra",
            "valor": Decimal("10.00"),
            "data_competencia": date(2026, 3, 1),
            "conta": self.conta,
            "categoria": self.categoria_despesa,
            "criado_por": self.user,
        }
        return Transacao(**{**padrao, **campos})

    def test_transferencia_exige_conta_destino(self):
        with self.assertRaises(ValidationError) as erro:
            self._transacao(tipo="transferencia", categoria=None).clean()

        self.assertIn("conta_destino", erro.exception.message_dict)

    def test_transferencia_recusa_destino_igual_a_origem(self):
        with self.assertRaises(ValidationError) as erro:
            self._transacao(tipo="transferencia", categoria=None, conta_destino=self.conta).clean()

        self.assertIn("diferente da conta origem", str(erro.exception))

    def test_transferencia_nao_usa_categoria(self):
        with self.assertRaises(ValidationError) as erro:
            self._transacao(tipo="transferencia", conta_destino=self.outra).clean()

        self.assertIn("categoria", erro.exception.message_dict)

    def test_conta_destino_so_vale_em_transferencia(self):
        with self.assertRaises(ValidationError) as erro:
            self._transacao(conta_destino=self.outra).clean()

        self.assertIn("conta_destino", erro.exception.message_dict)

    def test_transacao_comum_exige_categoria(self):
        with self.assertRaises(ValidationError) as erro:
            self._transacao(categoria=None).clean()

        self.assertIn("Informe a categoria", str(erro.exception))

    def test_categoria_precisa_ter_o_tipo_da_transacao(self):
        receita = CategoriaFinanceira.objects.create(nome="Salário", tipo="receita")

        with self.assertRaises(ValidationError) as erro:
            self._transacao(categoria=receita).clean()

        self.assertIn("mesmo tipo da transação", str(erro.exception))

    def test_save_valida_antes_de_gravar(self):
        """`save()` chama full_clean(): gravar inválido tem de levantar, não persistir."""
        with self.assertRaises(ValidationError):
            self._transacao(conta_destino=self.outra).save()

        self.assertFalse(Transacao.objects.exists())

    def test_transacao_valida_e_gravada(self):
        self._transacao().save()

        self.assertEqual(Transacao.objects.count(), 1)


class FaturaELancamentoTests(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(username="cartao", password=SENHA_TESTE)
        self.conta = Conta.objects.create(nome="Corrente", saldo_inicial=Decimal("0.00"))
        self.cartao = CartaoCredito.objects.create(
            nome="Principal",
            limite=Decimal("1000.00"),
            dia_fechamento=20,
            dia_vencimento=28,
            conta_pagamento=self.conta,
        )
        self.categoria = CategoriaFinanceira.objects.create(nome="Mercado", tipo="despesa")

    def test_fatura_herda_a_conta_de_pagamento_do_cartao(self):
        """Sem isto a fatura nasce sem conta e o pagamento não sabe de onde sair."""
        fatura = FaturaCartao(cartao=self.cartao, mes=3, ano=2026)

        fatura.save()

        self.assertEqual(fatura.conta_pagamento, self.conta)

    def test_categoria_de_pagamento_precisa_ser_de_despesa(self):
        receita = CategoriaFinanceira.objects.create(nome="Salário", tipo="receita")
        fatura = FaturaCartao(cartao=self.cartao, mes=3, ano=2026, categoria_pagamento=receita)

        with self.assertRaises(ValidationError) as erro:
            fatura.clean()

        self.assertIn("categoria_pagamento", erro.exception.message_dict)

    def test_valor_total_ignora_lancamento_cancelado(self):
        fatura = FaturaCartao.objects.create(cartao=self.cartao, mes=3, ano=2026)
        for valor, status in ((Decimal("30.00"), "ativo"), (Decimal("70.00"), "cancelado")):
            LancamentoCartao.objects.create(
                fatura=fatura,
                cartao=self.cartao,
                categoria=self.categoria,
                descricao="Compra",
                valor=valor,
                status=status,
                criado_por=self.user,
            )

        self.assertEqual(fatura.valor_total, Decimal("30.00"))

    def test_lancamento_recusa_parcela_maior_que_o_total(self):
        fatura = FaturaCartao.objects.create(cartao=self.cartao, mes=3, ano=2026)
        lancamento = LancamentoCartao(
            fatura=fatura,
            cartao=self.cartao,
            categoria=self.categoria,
            descricao="Compra",
            valor=Decimal("10.00"),
            parcela_numero=4,
            parcela_total=3,
            criado_por=self.user,
        )

        with self.assertRaises(ValidationError) as erro:
            lancamento.save()

        self.assertIn("parcela_numero", erro.exception.message_dict)

    def test_lancamento_recusa_fatura_de_outro_cartao(self):
        outro = CartaoCredito.objects.create(
            nome="Secundário", limite=Decimal("500.00"), dia_fechamento=10, dia_vencimento=18
        )
        fatura_do_outro = FaturaCartao.objects.create(cartao=outro, mes=3, ano=2026)
        lancamento = LancamentoCartao(
            fatura=fatura_do_outro,
            cartao=self.cartao,
            categoria=self.categoria,
            descricao="Compra",
            valor=Decimal("10.00"),
            criado_por=self.user,
        )

        with self.assertRaises(ValidationError) as erro:
            lancamento.save()

        self.assertIn("fatura", erro.exception.message_dict)


class RecorrenciaFinanceiraTests(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(username="recorrente", password=SENHA_TESTE)
        self.conta = Conta.objects.create(nome="Corrente", saldo_inicial=Decimal("0.00"))
        self.categoria = CategoriaFinanceira.objects.create(nome="Aluguel", tipo="despesa")

    def _recorrencia(self, **campos):
        padrao = {
            "tipo": "despesa",
            "descricao": "Aluguel",
            "valor": Decimal("1500.00"),
            "categoria": self.categoria,
            "conta": self.conta,
            "dia_vencimento": 5,
            "data_inicio": date(2026, 1, 1),
            "criado_por": self.user,
        }
        return RecorrenciaFinanceira(**{**padrao, **campos})

    def test_categoria_precisa_ter_o_tipo_da_recorrencia(self):
        receita = CategoriaFinanceira.objects.create(nome="Salário", tipo="receita")

        with self.assertRaises(ValidationError) as erro:
            self._recorrencia(categoria=receita).save()

        self.assertIn("categoria", erro.exception.message_dict)

    def test_data_final_nao_pode_preceder_a_inicial(self):
        with self.assertRaises(ValidationError) as erro:
            self._recorrencia(data_fim=date(2025, 12, 1)).save()

        self.assertIn("data_fim", erro.exception.message_dict)

    def test_recorrencia_valida_e_gravada(self):
        self._recorrencia(data_fim=date(2026, 12, 1)).save()

        self.assertEqual(RecorrenciaFinanceira.objects.count(), 1)


class MetaFinanceiraValorAtualTests(TestCase):
    def test_meta_sem_conta_usa_o_valor_manual(self):
        meta = MetaFinanceira.objects.create(
            nome="Viagem", valor_alvo=Decimal("1000.00"), valor_atual_manual=Decimal("250.00")
        )

        self.assertEqual(meta.valor_atual, Decimal("250.00"))
        self.assertEqual(meta.percentual_concluido, Decimal("25.00"))

    def test_meta_vinculada_segue_o_saldo_da_conta(self):
        """Vinculada a uma conta, o valor manual deixa de valer — quem manda é o saldo."""
        conta = Conta.objects.create(nome="Reserva", saldo_inicial=Decimal("800.00"))
        meta = MetaFinanceira.objects.create(
            nome="Viagem",
            valor_alvo=Decimal("1000.00"),
            valor_atual_manual=Decimal("250.00"),
            conta_vinculada=conta,
        )

        self.assertEqual(meta.valor_atual, conta.saldo_atual())
        self.assertEqual(meta.valor_atual, Decimal("800.00"))
