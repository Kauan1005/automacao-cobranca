"""Relatório diário: gasto do que saiu e economia do que a trava segurou, por canal e faixa."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


def resumo(con: sqlite3.Connection) -> list[dict]:
    """Uma linha por canal e faixa com enviados, bloqueados, gasto, economia e % economizado."""
    linhas = con.execute(
        """
        WITH enviados AS (
            SELECT canal, faixa, COUNT(*) AS qtd, SUM(custo) AS gasto FROM fila GROUP BY canal, faixa
        ), bloqueados AS (
            SELECT b.canal, f.faixa, COUNT(*) AS qtd, SUM(b.custo) AS economia
            FROM bloqueio AS b JOIN fila_original AS f ON f.contato_id = b.contato_id AND f.canal = b.canal
            GROUP BY b.canal, f.faixa
        )
        SELECT o.canal, o.faixa,
               COALESCE(e.qtd, 0), COALESCE(b.qtd, 0), COALESCE(e.gasto, 0), COALESCE(b.economia, 0)
        FROM (SELECT DISTINCT canal, faixa FROM fila_original) AS o
        LEFT JOIN enviados AS e ON e.canal = o.canal AND e.faixa = o.faixa
        LEFT JOIN bloqueados AS b ON b.canal = o.canal AND b.faixa = o.faixa
        ORDER BY o.canal, o.faixa
        """
    ).fetchall()
    out = []
    for canal, faixa, env, bloq, gasto, econ in linhas:
        total = gasto + econ
        out.append({"canal": canal, "faixa": faixa, "enviados": env, "bloqueados": bloq,
                    "gasto": round(gasto, 2), "economia": round(econ, 2),
                    "economia_pct": round(econ / total, 4) if total else 0.0})
    return out


def salvar_excel(linhas: list[dict], motivos: dict[str, int], destino: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    cab = ["Canal", "Faixa", "Enviados", "Bloqueados", "Gasto (R$)", "Economia (R$)", "% economizado"]
    ws.append(cab)
    for r in linhas:
        ws.append([r["canal"], r["faixa"], r["enviados"], r["bloqueados"], r["gasto"], r["economia"], r["economia_pct"]])
    n = len(linhas) + 1
    ws.append(["Total", "", f"=SUM(C2:C{n})", f"=SUM(D2:D{n})", f"=SUM(E2:E{n})", f"=SUM(F2:F{n})",
               f"=IFERROR(F{n + 1}/(E{n + 1}+F{n + 1}),0)"])
    for cel in ws[1]:
        cel.font = Font(bold=True, color="FFFFFF")
        cel.fill = PatternFill("solid", fgColor="1D2024")
    for cel in ws[n + 1]:
        cel.font = Font(bold=True)
    for linha in ws.iter_rows(min_row=2):
        linha[4].number_format = linha[5].number_format = '"R$" #,##0.00'
        linha[6].number_format = "0.0%"
    for i, largura in enumerate([12, 12, 11, 12, 14, 15, 15], start=1):
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws2 = wb.create_sheet("Descartes e bloqueios")
    ws2.append(["Motivo", "Quantidade"])
    for motivo, qtd in sorted(motivos.items(), key=lambda kv: -kv[1]):
        ws2.append([motivo, qtd])
    ws2.column_dimensions["A"].width = 34
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    return destino
