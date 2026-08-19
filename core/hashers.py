"""Hasher de senha usado só pela suíte de testes."""

from django.contrib.auth.hashers import PBKDF2PasswordHasher


class PBKDF2RapidoParaTestes(PBKDF2PasswordHasher):
    """Mesmo algoritmo da produção, com fator de trabalho mínimo.

    Trocar o hasher por MD5 é o atalho clássico para a suíte não gastar tempo
    derivando chave — era o que estava aqui. O custo é que um algoritmo
    quebrado passa a existir no repositório: os scanners acusam com razão, e
    basta alguém mover a linha para fora do bloco de teste para a produção
    herdar MD5. Baixar as iterações do PBKDF2 dá a mesma economia sem trazer
    algoritmo inseguro para dentro do código.
    """

    iterations = 1
