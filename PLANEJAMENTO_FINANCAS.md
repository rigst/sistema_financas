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
- Importação e exportação CSV de transações.
- Índices de consulta para transações, faturas e lançamentos de cartão.
- Pagamento de fatura protegido por transação atômica.
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

1. Criar importação específica de faturas de cartão.
2. Adicionar anexos de comprovantes.
3. Melhorar gráficos do dashboard.
4. Criar página de configuração financeira para conta/categoria padrão.
5. Evoluir saldos materializados se o volume de transações exigir.
