"""Gera uma carteira e um histórico de envios 100% fictícios (semente fixa, sempre o mesmo resultado).

Uso: python dados/gerar_exemplo.py
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

AQUI = Path(__file__).parent
NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela", "Hugo", "Isabela", "João", "Karen",
         "Lucas", "Marina", "Nuno", "Olívia", "Paulo", "Rafaela", "Sérgio", "Tatiane", "Vitor"]
SOBRENOMES = ["Silva", "Souza", "Oliveira", "Santos", "Lima", "Pereira", "Costa", "Rocha", "Almeida", "Nunes"]
EMPRESAS = ["Comercial", "Transportes", "Serviços", "Distribuidora", "Mecânica"]
DDDS = [11, 11, 11, 12, 13, 19, 21, 31, 41, 51, 61, 71, 81]


def _dv(base: list[int], pesos: list[int]) -> int:
    r = sum(a * b for a, b in zip(base, pesos, strict=True)) % 11
    return 0 if r < 2 else 11 - r


def cpf(rng: random.Random) -> str:
    b = [rng.randint(0, 9) for _ in range(9)]
    b.append(_dv(b, list(range(10, 1, -1))))
    b.append(_dv(b, list(range(11, 1, -1))))
    return "".join(map(str, b))


def cnpj(rng: random.Random) -> str:
    b = [rng.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    p = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    b.append(_dv(b, p))
    b.append(_dv(b, [6, *p]))
    return "".join(map(str, b))


def celular(rng: random.Random) -> str:
    return f"({rng.choice(DDDS)}) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"


def gerar(n: int = 600, semente: int = 42) -> None:
    rng = random.Random(semente)
    linhas = []
    for i in range(n):
        pj = rng.random() < 0.2
        doc = cnpj(rng) if pj else cpf(rng)
        nome = f"{rng.choice(SOBRENOMES)} {rng.choice(EMPRESAS)} Ltda" if pj else f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}"
        r = rng.random()
        # sujeira típica de planilha: pontuação, zero perdido, documento inválido, telefone fixo ou vazio
        if r < 0.05:
            doc = doc[:-1] + str((int(doc[-1]) + 1) % 10)
        elif r < 0.25:
            doc = doc.lstrip("0")
        elif r < 0.45 and not pj:
            doc = f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        tel1 = rng.choice([celular(rng), celular(rng), f"(11) 3{rng.randint(100, 999)}-{rng.randint(1000, 9999)}", ""])
        linhas.append({
            "contrato": f"CT{100000 + i}",
            "nome": nome.upper() if rng.random() < 0.3 else nome,
            "documento": doc,
            "telefone_1": tel1,
            "telefone_2": celular(rng) if rng.random() < 0.6 else "",
            "telefone_3": "",
            "dias_atraso": rng.choice([rng.randint(0, 4), rng.randint(5, 30), rng.randint(31, 120), rng.randint(121, 990), rng.randint(991, 1500)]),
            "valor_aberto": f"{rng.uniform(80, 9000):.2f}".replace(".", ","),
        })
    # alguns contratos repetidos da mesma pessoa
    for _ in range(30):
        d = dict(rng.choice(linhas))
        d["contrato"] = f"CT{rng.randint(200000, 299999)}"
        d["dias_atraso"] = rng.randint(5, 400)
        linhas.append(d)

    with (AQUI / "carteira_exemplo.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        w.writeheader()
        w.writerows(linhas)

    # histórico: parte da carteira já recebeu mensagem nos últimos dias
    from cobranca.documentos import normalizar_documento  # noqa: PLC0415
    hoje = date(2026, 10, 26)
    hist = []
    for ln in rng.sample(linhas, 160):
        doc = normalizar_documento(ln["documento"])
        if doc:
            canal = "RCS" if int(ln["dias_atraso"]) <= 4 else "WHATSAPP"
            hist.append({"contato_id": doc[1], "canal": canal, "enviado_em": (hoje - timedelta(days=rng.randint(0, 6))).isoformat()})
    with (AQUI / "historico_exemplo.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["contato_id", "canal", "enviado_em"], delimiter=";")
        w.writeheader()
        w.writerows(hist)

    # respostas à campanha anterior, escritas do jeito que as pessoas escrevem
    resp = []
    for i, ln in enumerate(rng.sample(linhas, 90)):
        doc = normalizar_documento(ln["documento"])
        if doc:
            resp.append({"id": f"R{i + 1:03d}", "contato_id": doc[1], "texto": rng.choice(RESPOSTAS)})
    with (AQUI / "respostas_exemplo.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "contato_id", "texto"], delimiter=";")
        w.writeheader()
        w.writerows(resp)
    print(f"{len(linhas)} contratos, {len(hist)} envios anteriores e {len(resp)} respostas gerados em {AQUI}")


RESPOSTAS = [
    "Já paguei ontem, vou mandar o comprovante",
    "paguei semana passada",
    "Quero fazer um acordo, dá pra parcelar?",
    "tem desconto pra pagar à vista?",
    "Me manda o boleto por favor",
    "pode mandar o pix?",
    "Não sou eu, número errado",
    "não conheço esse contrato, engano",
    "Para de me mandar mensagem",
    "não me mande mais nada",
    "ok",
    "quem é?",
    "vou ver e te retorno",
]


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(AQUI.parent))
    gerar()
