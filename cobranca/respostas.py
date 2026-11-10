"""Classificação das respostas dos clientes às campanhas.

Quem responde "já paguei", "número errado" ou "pare de me mandar mensagem"
não deve receber a próxima campanha. Este módulo lê as respostas e decide a
intenção de cada uma, de dois jeitos:

- com IA (Claude), quando há credencial da Anthropic configurada;
- por regras de palavras-chave, quando não há (é o que roda nos testes e na CI).

As duas formas devolvem o mesmo formato, então o resto do pipeline não muda.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass

INTENCOES = ("ja_pagou", "quer_negociar", "pediu_boleto", "numero_errado", "pediu_para_parar", "outro")

# o que cada intenção faz na próxima campanha
BLOQUEIA = {
    "ja_pagou": "cliente informou pagamento",
    "numero_errado": "número não é do cliente",
    "pediu_para_parar": "cliente pediu para parar",
}
ENCAMINHA = {"quer_negociar", "pediu_boleto"}  # vai para o atendimento humano

MODELO = "claude-opus-5-5"
LOTE = 50

INSTRUCOES = (
    "Você classifica respostas de clientes a mensagens de cobrança enviadas por WhatsApp. "
    "Para cada resposta, escolha uma intenção: "
    "ja_pagou (diz que já pagou ou mandou comprovante), "
    "quer_negociar (quer acordo, desconto ou parcelar), "
    "pediu_boleto (pede boleto, código de barras ou PIX), "
    "numero_errado (diz que não é a pessoa ou não conhece o contrato), "
    "pediu_para_parar (pede para não receber mais mensagens), "
    "outro (qualquer outra coisa). "
    "Na dúvida entre bloquear e não bloquear, escolha outro."
)

ESQUEMA = {
    "type": "object",
    "properties": {
        "itens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "intencao": {"type": "string", "enum": list(INTENCOES)},
                },
                "required": ["id", "intencao"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["itens"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Resposta:
    id: str
    contato_id: str
    texto: str


@dataclass(frozen=True)
class Classificacao:
    id: str
    contato_id: str
    intencao: str
    origem: str  # "ia" ou "regras"


# ---------- regras ----------

def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


REGRAS = (
    ("pediu_para_parar", r"\b(para de|pare|parem|nao (me )?mand|sair da lista|descadastr|bloque)"),
    ("numero_errado", r"\b(nao sou|numero errado|nao conheco|engano|nao e (o|a) )"),
    ("ja_pagou", r"\b(ja pag|paguei|quitei|comprovante|ja foi pago)"),
    ("pediu_boleto", r"\b(boleto|codigo de barras|pix|linha digitavel)"),
    ("quer_negociar", r"\b(acordo|negociar|parcel|desconto|proposta)"),
)


def classificar_por_regras(respostas: list[Resposta]) -> list[Classificacao]:
    """Classificação simples por palavras-chave. A ordem das regras importa:
    pedir para parar vale mais do que qualquer outra intenção na mesma frase."""
    saida = []
    for r in respostas:
        texto = _normalizar(r.texto)
        intencao = next((nome for nome, padrao in REGRAS if re.search(padrao, texto)), "outro")
        saida.append(Classificacao(r.id, r.contato_id, intencao, "regras"))
    return saida


# ---------- IA ----------

def classificar_com_ia(respostas: list[Resposta], cliente=None) -> list[Classificacao]:
    """Classifica com o Claude, em lotes, com saída em JSON validada por esquema.

    `cliente` permite injetar um cliente falso nos testes. Sem ele, cria o
    cliente oficial da Anthropic, que lê a credencial do ambiente.
    """
    if cliente is None:
        import anthropic  # dependência opcional: pip install anthropic

        cliente = anthropic.Anthropic()
    por_id = {r.id: r for r in respostas}
    saida: list[Classificacao] = []
    for i in range(0, len(respostas), LOTE):
        lote = respostas[i:i + LOTE]
        conteudo = "\n".join(json.dumps({"id": r.id, "texto": r.texto}, ensure_ascii=False) for r in lote)
        resp = cliente.beta.messages.create(
            model=MODELO,
            max_tokens=4096,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=INSTRUCOES,
            messages=[{"role": "user", "content": conteudo}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
        )
        if resp.stop_reason == "refusal":
            # lote recusado: cai para as regras em vez de deixar sem classificação
            saida.extend(classificar_por_regras(lote))
            continue
        texto = next(b.text for b in resp.content if b.type == "text")
        vistos = set()
        for item in json.loads(texto)["itens"]:
            r = por_id.get(item["id"])
            if r and r.id not in vistos:
                vistos.add(r.id)
                saida.append(Classificacao(r.id, r.contato_id, item["intencao"], "ia"))
        # o que o modelo não devolveu também cai para as regras
        saida.extend(classificar_por_regras([r for r in lote if r.id not in vistos]))
    return saida


def classificar(respostas: list[Resposta], usar_ia: bool = False, cliente=None) -> list[Classificacao]:
    return classificar_com_ia(respostas, cliente) if usar_ia else classificar_por_regras(respostas)


def bloqueios(classificacoes: list[Classificacao]) -> dict[str, str]:
    """contato_id -> motivo, para quem não deve receber a próxima campanha."""
    return {c.contato_id: BLOQUEIA[c.intencao] for c in classificacoes if c.intencao in BLOQUEIA}


def para_atendimento(classificacoes: list[Classificacao]) -> list[str]:
    """Contatos que pediram boleto ou negociação: vão para um atendente."""
    return sorted({c.contato_id for c in classificacoes if c.intencao in ENCAMINHA})
