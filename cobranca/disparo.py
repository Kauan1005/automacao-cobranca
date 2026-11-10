"""Montagem das campanhas e envio por API REST, em lotes.

O endpoint é fictício. Por padrão o cliente roda em modo simulado (dry run): grava o JSON que seria
enviado, em vez de chamar a API. Para um envio real, defina COBRANCA_API_URL e COBRANCA_API_TOKEN.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .limpeza import Contato
from .segmentacao import Segmento

TAMANHO_LOTE = 1000


def payload_campanha(seg: Segmento, contatos: list[Contato], hoje: date) -> dict:
    """Corpo da criação de campanha: nome, canal, modelo de mensagem e contatos com as variáveis do modelo."""
    return {
        "campanha": {
            "nome": f"COBRANCA_{seg.canal}_{seg.faixa.replace(' ', '')}_{hoje:%Y%m%d}",
            "canal": seg.canal,
            "modelo": f"cobranca_{seg.faixa.split()[0].lower()}",
        },
        "contatos": [
            {
                "telefone": c.celular,
                "variaveis": {"nome": c.nome.split()[0], "contrato": c.contrato, "valor": f"{c.valor_aberto:.2f}"},
            }
            for c in contatos
        ],
    }


def lotes(itens: list, tamanho: int = TAMANHO_LOTE):
    for i in range(0, len(itens), tamanho):
        yield itens[i:i + tamanho]


@dataclass
class ClienteApi:
    saida: Path
    dry_run: bool = True

    def enviar(self, corpo: dict) -> dict:
        if self.dry_run:
            self.saida.mkdir(parents=True, exist_ok=True)
            arquivo = self.saida / f"{corpo['campanha']['nome']}_{len(list(self.saida.iterdir())):03d}.json"
            arquivo.write_text(json.dumps(corpo, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"status": "simulado", "arquivo": str(arquivo), "contatos": len(corpo["contatos"])}
        url = os.environ["COBRANCA_API_URL"].rstrip("/") + "/campanhas"
        if not url.startswith("https://"):
            raise ValueError("COBRANCA_API_URL precisa usar https://")
        req = urllib.request.Request(  # noqa: S310 (esquema validado acima)
            url,
            data=json.dumps(corpo).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {os.environ['COBRANCA_API_TOKEN']}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (esquema validado acima)
            return json.load(resp)
