import json
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from cobranca.respostas import (  # noqa: E402
    Resposta,
    bloqueios,
    classificar_com_ia,
    classificar_por_regras,
    para_atendimento,
)
from cobranca.trava import aplicar_respostas, conectar  # noqa: E402


def r(texto, n="1"):
    return Resposta(n, f"DOC{n}", texto)


class Regras(unittest.TestCase):
    CASOS = {
        "Já paguei ontem, segue o comprovante": "ja_pagou",
        "QUITEI essa dívida": "ja_pagou",
        "quero fazer um acordo": "quer_negociar",
        "dá pra parcelar em 3x?": "quer_negociar",
        "me manda o boleto": "pediu_boleto",
        "pode ser pix?": "pediu_boleto",
        "não sou eu, número errado": "numero_errado",
        "não conheço esse contrato": "numero_errado",
        "para de me mandar mensagem": "pediu_para_parar",
        "NÃO ME MANDE MAIS NADA": "pediu_para_parar",
        "ok": "outro",
        "quem é?": "outro",
    }

    def test_intencoes(self):
        for texto, esperado in self.CASOS.items():
            with self.subTest(texto=texto):
                self.assertEqual(classificar_por_regras([r(texto)])[0].intencao, esperado)

    def test_parar_vence_outras_intencoes(self):
        # pede boleto e pede para parar na mesma frase: parar tem prioridade
        self.assertEqual(classificar_por_regras([r("não quero boleto, para de mandar")])[0].intencao, "pediu_para_parar")

    def test_bloqueios_e_atendimento(self):
        c = classificar_por_regras([r("já paguei", "1"), r("me manda o boleto", "2"), r("ok", "3"), r("pare", "4")])
        self.assertEqual(bloqueios(c), {"DOC1": "cliente informou pagamento", "DOC4": "cliente pediu para parar"})
        self.assertEqual(para_atendimento(c), ["DOC2"])


class ClienteFalso:
    """Imita client.beta.messages.create sem chamar a API."""

    def __init__(self, resposta_json=None, recusa=False):
        self.chamadas = []
        self.resposta_json = resposta_json
        self.recusa = recusa
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.recusa:
            return SimpleNamespace(stop_reason="refusal", content=[])
        bloco = SimpleNamespace(type="text", text=json.dumps(self.resposta_json))
        return SimpleNamespace(stop_reason="end_turn", content=[bloco])


class ComIA(unittest.TestCase):
    def test_usa_saida_estruturada_e_o_que_faltar_cai_nas_regras(self):
        cliente = ClienteFalso({"itens": [{"id": "1", "intencao": "quer_negociar"}]})
        c = classificar_com_ia([r("tem como ver isso pra mim?", "1"), r("já paguei", "2")], cliente)
        self.assertEqual([(x.id, x.intencao, x.origem) for x in c], [("1", "quer_negociar", "ia"), ("2", "ja_pagou", "regras")])
        chamada = cliente.chamadas[0]
        self.assertEqual(chamada["model"], "claude-opus-5-5")
        self.assertEqual(chamada["output_config"]["format"]["type"], "json_schema")

    def test_recusa_cai_nas_regras(self):
        c = classificar_com_ia([r("já paguei")], ClienteFalso(recusa=True))
        self.assertEqual((c[0].intencao, c[0].origem), ("ja_pagou", "regras"))

    def test_lotes_de_50(self):
        cliente = ClienteFalso({"itens": []})
        classificar_com_ia([r("ok", str(i)) for i in range(120)], cliente)
        self.assertEqual(len(cliente.chamadas), 3)


class TravaComRespostas(unittest.TestCase):
    def test_tira_da_fila_quem_pediu(self):
        con = conectar()
        con.executemany("INSERT INTO fila VALUES (?, ?, ?, ?)", [("A", "WHATSAPP", "05 a 30", 0.3), ("B", "WHATSAPP", "05 a 30", 0.3)])
        self.assertEqual(aplicar_respostas(con, {"A": "cliente pediu para parar"}, date(2026, 10, 26)), 1)
        self.assertEqual([x[0] for x in con.execute("SELECT contato_id FROM fila")], ["B"])
        self.assertEqual(con.execute("SELECT motivo FROM bloqueio").fetchone()[0], "resposta: cliente pediu para parar")


if __name__ == "__main__":
    unittest.main()
