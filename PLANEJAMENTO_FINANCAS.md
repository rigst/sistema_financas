# Planejamento do Sistema de Finanças

## Implementado

- App `financeiro` como domínio principal e único do produto.
- Contas financeiras.
- Categorias de receita e despesa.
- Transações de receita, despesa e transferência.
- Dashboard financeiro.
- Cartões de crédito.
- Faturas de cartão.
- Compras parceladas no cartão.
- Pagamento de fatura com geração de transação bancária.
- Planejamento mensal por categoria.
- Metas financeiras.
- Recorrências financeiras.
- Relatório mensal de fluxo de caixa.
- Testes de regras principais.
- Remoção dos módulos comerciais herdados do projeto anterior.

## Regras centrais

- Receita paga aumenta saldo da conta.
- Despesa paga reduz saldo da conta.
- Transação pendente entra como previsão, mas não altera saldo realizado.
- Transferência reduz a conta origem e aumenta a conta destino.
- Compra no cartão aumenta a fatura, mas não reduz conta bancária no momento da compra.
- Pagamento de fatura reduz a conta bancária.
- Fatura paga não aceita novos lançamentos.
- Fatura sem valor não pode ser paga.
- Transações canceladas não entram nos cálculos.

## Próximas melhorias recomendadas

1. Melhorar performance dos saldos com agregações SQL ou saldos materializados.
2. Criar exportação CSV/XLSX para relatórios financeiros.
3. Adicionar importação de extratos bancários e faturas.
4. Adicionar anexos de comprovantes.
5. Melhorar gráficos do dashboard.
6. Criar página de configuração financeira para conta/categoria padrão.
