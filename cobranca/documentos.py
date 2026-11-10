"""Normalização e validação de CPF e CNPJ (dígitos verificadores)."""

from __future__ import annotations

import re

_SO_DIGITOS = re.compile(r"\D")


def so_digitos(valor: str | int | None) -> str:
    """Remove pontuação e espaços. Planilhas costumam perder o zero à esquerda, então ele é recolocado depois."""
    if valor is None:
        return ""
    return _SO_DIGITOS.sub("", str(valor))


def _digito(base: str, pesos: list[int]) -> str:
    resto = sum(int(d) * p for d, p in zip(base, pesos, strict=True)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    d1 = _digito(cpf[:9], list(range(10, 1, -1)))
    d2 = _digito(cpf[:9] + d1, list(range(11, 1, -1)))
    return cpf[-2:] == d1 + d2


def cnpj_valido(cnpj: str) -> bool:
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = _digito(cnpj[:12], p1)
    d2 = _digito(cnpj[:12] + d1, [6, *p1])
    return cnpj[-2:] == d1 + d2


def normalizar_documento(valor: str | int | None) -> tuple[str, str] | None:
    """Devolve (tipo, documento) com zeros à esquerda, ou None se o documento for inválido.

    >>> normalizar_documento("529.982.247-25")
    ('cpf', '52998224725')
    """
    d = so_digitos(valor)
    if not d:
        return None
    if len(d) <= 11 and cpf_valido(d.zfill(11)):
        return "cpf", d.zfill(11)
    if len(d) <= 14 and cnpj_valido(d.zfill(14)):
        return "cnpj", d.zfill(14)
    return None
