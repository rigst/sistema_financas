# Planejamento do Sistema de Finanças

## Direção

Criar um sistema de controle pessoal de finanças mantendo o design e a infraestrutura do `sistema_orcamentos`, mas substituindo o domínio de clientes/orçamentos por contas, lançamentos, cartões, planejamento mensal e relatórios financeiros.

## Reaproveitar

- Autenticação e usuários
- Layout base e CSS
- Mensagens, formulários, tabelas e botões
- Máscaras de moeda, telefone, CPF/CNPJ e CEP
- Segurança, middleware e configurações de produção
- Padrão de views, forms, urls e templates dos CRUDs existentes

## Substituir gradualmente

- `clientes` por contatos opcionais ou remover do MVP
- `catalogo` por categorias financeiras
- `orcamentos` por transações, contas e planejamento
- `relatorios` por relatórios financeiros

## Entidades do MVP

### Conta

Representa onde o dinheiro está.

Campos previstos:

- nome
- tipo
- instituicao
- saldo_inicial
- data_saldo_inicial
- cor
- ativa
- empresa/grupo
- criado_em
- atualizado_em

### CategoriaFinanceira

Classifica receitas e despesas.

Campos previstos:

- nome
- tipo: receita ou despesa
- categoria_pai
- cor
- icone
- ativa
- empresa/grupo
- criado_em
- atualizado_em

### Transacao

Movimentação financeira principal.

Campos previstos:

- tipo: receita, despesa ou transferencia
- descricao
- valor
- data_competencia
- data_pagamento
- status: pendente, pago, cancelado
- conta
- conta_destino para transferencias
- categoria
- observacoes
- criado_por
- empresa/grupo
- criado_em
- atualizado_em

## Entidades da segunda fase

### CartaoCredito

- nome
- bandeira
- limite
- dia_fechamento
- dia_vencimento
- conta_pagamento
- cor
- ativo

### FaturaCartao

- cartao
- mes_referencia
- data_fechamento
- data_vencimento
- status
- valor_total
- valor_pago
- conta_pagamento
- data_pagamento

### OrcamentoMensal

- mes
- ano
- categoria
- valor_planejado
- empresa/grupo

### MetaFinanceira

- nome
- valor_alvo
- valor_atual_manual
- data_inicio
- data_limite
- conta_vinculada
- status
- cor
- observacoes

## Regras centrais

- Receita paga aumenta saldo da conta.
- Despesa paga reduz saldo da conta.
- Transação pendente entra em previsão, mas não altera saldo realizado.
- Transferência reduz a conta origem e aumenta a conta destino.
- Compra no cartão aumenta fatura, mas não reduz conta bancária no momento da compra.
- Pagamento de fatura reduz a conta bancária.
- Transações canceladas não entram nos cálculos.

## Ordem de implementação

1. Criar app `financeiro`.
2. Criar modelos `Conta`, `CategoriaFinanceira` e `Transacao`.
3. Registrar modelos no admin.
4. Criar migrations e testes de cálculo.
5. Implementar CRUD de contas.
6. Implementar CRUD de categorias.
7. Implementar CRUD de transações.
8. Adaptar dashboard para saldo, receitas, despesas e resultado do mês.
9. Criar relatórios básicos por mês, conta e categoria.
10. Implementar cartões e faturas na segunda fase.
