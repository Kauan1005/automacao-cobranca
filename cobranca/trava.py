"""Trava anti-reenvio.

No trabalho ela roda em T-SQL no SQL Server (veja sql/trava_envio.sql). Aqui a mesma regra roda em
SQLite, para o projeto funcionar e ser testado sem servidor: antes do disparo, quem já recebeu
mensagem no mesmo canal dentro do intervalo mínimo sai da fila, e o motivo fica registrado.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS historico (contato_id TEXT, canal TEXT, enviado_em TEXT);
CREATE TABLE IF NOT EXISTS fila (contato_id TEXT, canal TEXT, faixa TEXT, custo REAL);
CREATE TABLE IF NOT EXISTS bloqueio (contato_id TEXT, canal TEXT, motivo TEXT, custo REAL, registrado_em TEXT);
"""


def conectar(caminho: str = ":memory:") -> sqlite3.Connection:
    con = sqlite3.connect(caminho)
    con.executescript(SCHEMA)
    return con


def aplicar_trava(con: sqlite3.Connection, hoje: date, intervalo_dias: int = 3) -> int:
    """Move para `bloqueio` os itens da fila contatados nos últimos `intervalo_dias` e devolve quantos foram."""
    desde = (hoje - timedelta(days=intervalo_dias - 1)).isoformat()
    motivo = "já contatado hoje" if intervalo_dias == 1 else f"contatado nos últimos {intervalo_dias} dias"
    with con:
        con.execute(
            """
            INSERT INTO bloqueio (contato_id, canal, motivo, custo, registrado_em)
            SELECT f.contato_id, f.canal, ?, f.custo, ?
            FROM fila AS f
            WHERE EXISTS (
                SELECT 1 FROM historico AS h
                WHERE h.contato_id = f.contato_id AND h.canal = f.canal AND h.enviado_em >= ?
            )
            """,
            (motivo, hoje.isoformat(), desde),
        )
        cur = con.execute(
            """
            DELETE FROM fila
            WHERE EXISTS (
                SELECT 1 FROM bloqueio AS b
                WHERE b.contato_id = fila.contato_id AND b.canal = fila.canal AND b.registrado_em = ?
            )
            """,
            (hoje.isoformat(),),
        )
    return cur.rowcount


def aplicar_respostas(con: sqlite3.Connection, bloqueios: dict[str, str], hoje: date) -> int:
    """Tira da fila quem respondeu que já pagou, que o número é errado ou que quer parar.

    `bloqueios` vem de respostas.bloqueios(): contato_id -> motivo.
    """
    alvo = [
        (contato_id, canal, f"resposta: {bloqueios[contato_id]}", custo, hoje.isoformat())
        for contato_id, canal, custo in con.execute("SELECT contato_id, canal, custo FROM fila")
        if contato_id in bloqueios
    ]
    with con:
        con.executemany("INSERT INTO bloqueio VALUES (?, ?, ?, ?, ?)", alvo)
        con.executemany("DELETE FROM fila WHERE contato_id = ? AND canal = ?", [(a[0], a[1]) for a in alvo])
    return len(alvo)
