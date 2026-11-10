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
from .segmentacao import segmentar
from .trava import aplicar_trava, conectar

# custo por mensagem, valores fictícios
CUSTO_POR_CANAL = {"WHATSAPP": 0.30, "RCS": 0.12}


def ler_csv(caminho: Path) -> list[dict]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def executar(entrada: Path, historico: Path | None, saida: Path, hoje: date, intervalo_dias: int = 3,
             dry_run: bool = True) -> dict:
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
    bloqueados = aplicar_trava(con, hoje, intervalo_dias)

    liberados: dict = {}
    for contato_id, canal in con.execute("SELECT contato_id, canal FROM fila"):
        seg, c = por_id[(contato_id, canal)]
        liberados.setdefault(seg, []).append(c)

    cliente = ClienteApi(saida / "envios", dry_run=dry_run)
    envios = [cliente.enviar(payload_campanha(seg, lote, hoje))
              for seg, contatos in liberados.items() for lote in lotes(contatos)]

    motivos = Counter(limpos.descartes)
    for (motivo, qtd) in con.execute("SELECT motivo, COUNT(*) FROM bloqueio GROUP BY motivo"):
        motivos[f"trava: {motivo}"] += qtd
    linhas = resumo(con)
    planilha = salvar_excel(linhas, dict(motivos), saida / f"relatorio_{hoje:%Y-%m-%d}.xlsx")
    return {"contatos_validos": len(limpos.contatos), "descartes": dict(limpos.descartes), "bloqueados": bloqueados,
            "lotes_enviados": len(envios), "resumo": linhas, "planilha": str(planilha)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Pipeline de cobrança com dados fictícios")
    ap.add_argument("--entrada", type=Path, default=Path("dados/carteira_exemplo.csv"))
    ap.add_argument("--historico", type=Path, default=Path("dados/historico_exemplo.csv"))
    ap.add_argument("--saida", type=Path, default=Path("saida"))
    ap.add_argument("--data", type=date.fromisoformat, default=date(2026, 10, 26))
    ap.add_argument("--intervalo", type=int, default=3, help="dias mínimos entre dois contatos no mesmo canal")
    args = ap.parse_args()
    r = executar(args.entrada, args.historico, args.saida, args.data, args.intervalo)
    gasto = sum(x["gasto"] for x in r["resumo"])
    economia = sum(x["economia"] for x in r["resumo"])
    print(f"contatos válidos: {r['contatos_validos']}  descartes: {r['descartes']}")
    print(f"bloqueados pela trava: {r['bloqueados']}  lotes enviados (simulado): {r['lotes_enviados']}")
    print(f"gasto: R$ {gasto:.2f}  economia: R$ {economia:.2f}  ({economia / (gasto + economia):.0%} do custo)")
    print(f"relatório: {r['planilha']}")


if __name__ == "__main__":
    main()
