import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from openpyxl import load_workbook  # noqa: E402

from cobranca.disparo import ClienteApi, lotes, payload_campanha  # noqa: E402
from cobranca.documentos import cnpj_valido, cpf_valido, normalizar_documento  # noqa: E402
from cobranca.limpeza import limpar  # noqa: E402
from cobranca.pipeline import executar  # noqa: E402
from cobranca.segmentacao import Segmento, segmentar, segmento_de  # noqa: E402
from cobranca.telefones import normalizar_celular  # noqa: E402
from cobranca.trava import aplicar_trava, conectar  # noqa: E402


class Documentos(unittest.TestCase):
    def test_cpf_e_cnpj(self):
        self.assertTrue(cpf_valido("52998224725"))
        self.assertFalse(cpf_valido("52998224726"))
        self.assertFalse(cpf_valido("11111111111"))
        self.assertTrue(cnpj_valido("11222333000181"))
        self.assertFalse(cnpj_valido("11222333000182"))

    def test_recoloca_zero_a_esquerda(self):
        self.assertEqual(normalizar_documento("191"), ("cpf", "00000000191"))  # planilha perdeu os zeros
        self.assertEqual(normalizar_documento("529.982.247-25"), ("cpf", "52998224725"))
        self.assertIsNone(normalizar_documento("123"))


class Telefones(unittest.TestCase):
    def test_formatos_aceitos(self):
        for entrada in ["(11) 98765-4321", "5511987654321", "011987654321", "11 8765-4321"]:
            with self.subTest(entrada=entrada):
                self.assertEqual(normalizar_celular(entrada), "5511987654321")

    def test_rejeita_fixo_ddd_invalido_e_repetido(self):
        self.assertIsNone(normalizar_celular("(11) 3456-7890"))
        self.assertIsNone(normalizar_celular("(20) 98765-4321"))
        self.assertIsNone(normalizar_celular("(11) 99999-9999"))
        self.assertIsNone(normalizar_celular(""))


class LimpezaESegmentacao(unittest.TestCase):
    LINHAS = [
        {"contrato": "A1", "nome": "ANA SILVA", "documento": "52998224725", "telefone_1": "(11) 98765-4321", "dias_atraso": "10", "valor_aberto": "100,50"},
        {"contrato": "A2", "nome": "Ana Silva", "documento": "529.982.247-25", "telefone_1": "(11) 98765-4321", "dias_atraso": "45", "valor_aberto": "300"},
        {"contrato": "B1", "nome": "Bruno", "documento": "52998224726", "telefone_1": "(11) 98765-1111", "dias_atraso": "10", "valor_aberto": "10"},
        {"contrato": "C1", "nome": "Carla", "documento": "11222333000181", "telefone_1": "(11) 3333-4444", "telefone_2": "", "dias_atraso": "3", "valor_aberto": "10"},
    ]

    def test_descartes_e_duplicados(self):
        r = limpar(self.LINHAS)
        self.assertEqual(len(r.contatos), 1)
        self.assertEqual(r.contatos[0].contrato, "A2")  # ficou o de maior atraso
        self.assertEqual(r.contatos[0].nome, "Ana Silva")
        self.assertEqual(r.descartes, {"duplicado": 1, "documento inválido": 1, "sem celular válido": 1})

    def test_limites_das_faixas(self):
        self.assertEqual(segmento_de(4), Segmento("AVISO", "RCS"))
        self.assertEqual(segmento_de(5).faixa, "05 a 30")
        self.assertEqual(segmento_de(30).faixa, "05 a 30")
        self.assertEqual(segmento_de(31).faixa, "31 a 120")
        self.assertEqual(segmento_de(990).faixa, "121 a 990")
        self.assertIsNone(segmento_de(991))

    def test_prioridade_por_valor(self):
        r = limpar([
            {"contrato": "X", "nome": "x", "documento": "52998224725", "telefone_1": "11987654321", "dias_atraso": "10", "valor_aberto": "50"},
            {"contrato": "Y", "nome": "y", "documento": "11222333000181", "telefone_1": "11912345678", "dias_atraso": "12", "valor_aberto": "900"},
        ])
        grupo = segmentar(r.contatos)[Segmento("05 a 30", "WHATSAPP")]
        self.assertEqual([c.contrato for c in grupo], ["Y", "X"])


class Trava(unittest.TestCase):
    def test_bloqueia_quem_ja_recebeu_no_mesmo_canal(self):
        con = conectar()
        con.executemany("INSERT INTO historico VALUES (?, ?, ?)", [
            ("A", "WHATSAPP", "2026-10-26"),  # hoje, mesmo canal -> bloqueia
            ("B", "RCS", "2026-10-26"),       # hoje, outro canal -> passa
            ("C", "WHATSAPP", "2026-10-20"),  # fora do intervalo -> passa
        ])
        con.executemany("INSERT INTO fila VALUES (?, ?, ?, ?)", [(x, "WHATSAPP", "05 a 30", 0.3) for x in "ABC"])
        self.assertEqual(aplicar_trava(con, date(2026, 10, 26), intervalo_dias=3), 1)
        self.assertEqual([r[0] for r in con.execute("SELECT contato_id FROM fila ORDER BY 1")], ["B", "C"])
        self.assertEqual(con.execute("SELECT contato_id, motivo FROM bloqueio").fetchall(), [("A", "contatado nos últimos 3 dias")])


class Disparo(unittest.TestCase):
    def test_payload_e_lotes(self):
        r = limpar(LimpezaESegmentacao.LINHAS[:1])
        corpo = payload_campanha(Segmento("05 a 30", "WHATSAPP"), r.contatos, date(2026, 10, 26))
        self.assertEqual(corpo["campanha"]["nome"], "COBRANCA_WHATSAPP_05a30_20261026")
        self.assertEqual(corpo["contatos"][0], {"telefone": "5511987654321", "variaveis": {"nome": "Ana", "contrato": "A1", "valor": "100.50"}})
        self.assertEqual([len(x) for x in lotes(list(range(2500)))], [1000, 1000, 500])

    def test_modo_simulado_grava_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = ClienteApi(Path(tmp), dry_run=True).enviar({"campanha": {"nome": "T"}, "contatos": [1, 2]})
            self.assertEqual(res["contatos"], 2)
            self.assertEqual(json.loads(Path(res["arquivo"]).read_text(encoding="utf-8"))["contatos"], [1, 2])


class PipelineCompleto(unittest.TestCase):
    def test_ponta_a_ponta_com_dados_de_exemplo(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = executar(RAIZ / "dados" / "carteira_exemplo.csv", RAIZ / "dados" / "historico_exemplo.csv",
                         Path(tmp), date(2026, 10, 26))
            self.assertGreater(r["contatos_validos"], 300)
            self.assertGreater(r["bloqueados"], 0)
            enviados = sum(x["enviados"] for x in r["resumo"])
            bloqueados = sum(x["bloqueados"] for x in r["resumo"])
            self.assertEqual(bloqueados, r["bloqueados"])
            for x in r["resumo"]:
                self.assertAlmostEqual(x["economia_pct"], x["economia"] / (x["gasto"] + x["economia"]), places=3)
            wb = load_workbook(r["planilha"])
            self.assertEqual(wb.sheetnames, ["Resumo", "Descartes e bloqueios"])
            self.assertEqual(sum(row[2] for row in wb["Resumo"].iter_rows(min_row=2, max_row=len(r["resumo"]) + 1, values_only=True)), enviados)


if __name__ == "__main__":
    unittest.main()
