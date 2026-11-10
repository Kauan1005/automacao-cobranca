"""Higienização da carteira: documento, telefones, deduplicação e registro do motivo de cada descarte."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .documentos import normalizar_documento
from .telefones import normalizar_celular


@dataclass(frozen=True)
class Contato:
    contrato: str
    nome: str
    tipo: str  # "cpf" ou "cnpj"
    documento: str
    celular: str
    dias_atraso: int
    valor_aberto: float


@dataclass
class ResultadoLimpeza:
    contatos: list[Contato] = field(default_factory=list)
    descartes: Counter = field(default_factory=Counter)


def _primeiro_celular(linha: dict) -> str | None:
    """A carteira traz até três telefones; usa o primeiro celular válido."""
    for coluna in ("telefone_1", "telefone_2", "telefone_3"):
        cel = normalizar_celular(linha.get(coluna))
        if cel:
            return cel
    return None


def limpar(linhas: list[dict]) -> ResultadoLimpeza:
    """Transforma as linhas brutas da carteira em contatos prontos para segmentar.

    Regras (as mesmas dos fluxos KNIME, aqui em Python):
      1. documento inválido -> descarta
      2. sem celular válido -> descarta
      3. mesmo documento em mais de um contrato -> fica só o de maior atraso (uma mensagem por pessoa)
    """
    res = ResultadoLimpeza()
    melhores: dict[str, Contato] = {}
    for linha in linhas:
        doc = normalizar_documento(linha.get("documento"))
        if not doc:
            res.descartes["documento inválido"] += 1
            continue
        cel = _primeiro_celular(linha)
        if not cel:
            res.descartes["sem celular válido"] += 1
            continue
        try:
            atraso = int(float(linha.get("dias_atraso") or 0))
            valor = round(float(str(linha.get("valor_aberto") or 0).replace(",", ".")), 2)
        except ValueError:
            res.descartes["valor ou atraso ilegível"] += 1
            continue
        c = Contato(str(linha.get("contrato", "")).strip(), str(linha.get("nome", "")).strip().title(),
                    doc[0], doc[1], cel, atraso, valor)
        chave = c.documento
        atual = melhores.get(chave)
        if atual is None:
            melhores[chave] = c
        else:
            res.descartes["duplicado"] += 1
            if c.dias_atraso > atual.dias_atraso:
                melhores[chave] = c
    res.contatos = list(melhores.values())
    return res
