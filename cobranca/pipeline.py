"""Pipeline completo: carteira (CSV) -> limpeza -> segmentação -> trava -> disparo -> relatório.

Uso:
    python -m cobranca.pipeline --entrada dados/carteira_exemplo.csv --historico dados/historico_exemplo.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path

from .disparo import ClienteApi, lotes, payload_campanha
from .limpeza import limpar
from .relatorio import resumo, salvar_excel
from .respostas import Resposta, bloqueios, classificar, para_atendimento
from .segmentacao import segmentar
from .trava import aplicar_respostas, aplicar_trava, conectar

# custo por mensagem, valores fictícios
CUSTO_POR_CANAL = {"WHATSAPP": 0.30, "RCS": 0.12}


def ler_csv(caminho: Path) -> list[dict]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def executar(entrada: Path, historico: Path | None, saida: Path, hoje: date, intervalo_dias: int = 3,
             dry_run: bool = True, respostas: Path | None = None, usar_ia: bool = False) -> dict:
    limpos = limpar(ler_csv(entrada))
    grupos = segmentar(limpos.contatos)

    con = conectar()
    if historico and historico.exists():
        con.executemany("INSERT INTO historico VALUES (:contato_id, :canal, :enviado_em)", ler_csv(historico))
    por_id = {}
    for seg, contatos in grupos.items():
        for c in contatos:
            por_id[(c.documento, seg.canal)] = (seg, c)
            con.execute("INSERT INTO fila VALUES (?, ?, ?, ?)", (c.documento, seg.canal, seg.faixa, CUSTO_POR_CANAL[seg.canal]))
    con.execute("CREATE TABLE fila_original AS SELECT * FROM fila")

    # respostas da última campanha: quem já pagou, número errado ou pediu para parar sai da fila
    atendimento: list[str] = []
    origem = None
    if respostas and respostas.exists():
        lidas = [Resposta(r["id"], r["contato_id"], r["texto"]) for r in ler_csv(respostas)]
        classes = classificar(lidas, usar_ia=usar_ia)
        origem = classes[0].origem if classes else None
        aplicar_respostas(con, bloqueios(classes), hoje)
        atendimento = para_atendimento(classes)
    aplicar_trava(con, hoje, intervalo_dias)
    bloqueados = con.execute("SELECT COUNT(*) FROM bloqueio").fetchone()[0]

    liberados: dict = {}
    for contato_id, canal in con.execute("SELECT contato_id, canal FROM fila"):
        seg, c = por_id[(contato_id, canal)]
        liberados.setdefault(seg, []).append(c)

    cliente = ClienteApi(saida / "envios", dry_run=dry_run)
    envios = [cliente.enviar(payload_campanha(seg, lote, hoje))
              for seg, contatos in liberados.items() for lote in lotes(contatos)]

    motivos = Counter(limpos.descartes)
    for (motivo, qtd) in con.execute("SELECT motivo, COUNT(*) FROM bloqueio GROUP BY motivo"):
        motivos[f"bloqueio: {motivo}"] += qtd
    linhas = resumo(con)
    planilha = salvar_excel(linhas, dict(motivos), saida / f"relatorio_{hoje:%Y-%m-%d}.xlsx")
    if atendimento:
        linhas_csv = ["contato_id", *atendimento]
        (saida / "para_atendimento.csv").write_text("\n".join(linhas_csv) + "\n", encoding="utf-8")
    return {"contatos_validos": len(limpos.contatos), "descartes": dict(limpos.descartes), "bloqueados": bloqueados,
            "lotes_enviados": len(envios), "resumo": linhas, "planilha": str(planilha),
            "para_atendimento": len(atendimento), "classificacao": origem}


def main() -> None:
    ap = argparse.ArgumentParser(description="Pipeline de cobrança com dados fictícios")
    ap.add_argument("--entrada", type=Path, default=Path("dados/carteira_exemplo.csv"))
    ap.add_argument("--historico", type=Path, default=Path("dados/historico_exemplo.csv"))
    ap.add_argument("--saida", type=Path, default=Path("saida"))
    ap.add_argument("--data", type=date.fromisoformat, default=date(2026, 10, 26))
    ap.add_argument("--intervalo", type=int, default=3, help="dias mínimos entre dois contatos no mesmo canal")
    ap.add_argument("--respostas", type=Path, default=Path("dados/respostas_exemplo.csv"))
    ap.add_argument("--ia", action="store_true", help="classifica as respostas com o Claude (precisa de credencial)")
    args = ap.parse_args()
    r = executar(args.entrada, args.historico, args.saida, args.data, args.intervalo,
                 respostas=args.respostas, usar_ia=args.ia)
    gasto = sum(x["gasto"] for x in r["resumo"])
    economia = sum(x["economia"] for x in r["resumo"])
    print(f"contatos válidos: {r['contatos_validos']}  descartes: {r['descartes']}")
    print(f"bloqueados (trava + respostas): {r['bloqueados']}  lotes enviados (simulado): {r['lotes_enviados']}")
    print(f"respostas classificadas por: {r['classificacao']}  encaminhados ao atendimento: {r['para_atendimento']}")
    print(f"gasto: R$ {gasto:.2f}  economia: R$ {economia:.2f}  ({economia / (gasto + economia):.0%} do custo)")
    print(f"relatório: {r['planilha']}")


if __name__ == "__main__":
    main()
