# Changelog

## 1.1.0

- Classificação das respostas dos clientes (`cobranca/respostas.py`): com o Claude e saída em JSON validada
  por esquema, ou por regras quando não há credencial.
- Quem respondeu que já pagou, que o número é errado ou que quer parar sai da próxima campanha
  (`trava.aplicar_respostas`); quem quer negociar ou pediu boleto vai para `para_atendimento.csv`.
- 7 testes novos (18 no total), sem chamadas reais à API.
- Linhas mais curtas em `documentos.py` e `sql/trava_envio.sql`.

## 1.0.0

- Pipeline completo com dados fictícios: limpeza de CPF/CNPJ e celulares, segmentação por faixa de atraso,
  trava anti-reenvio (T-SQL e SQLite), disparo simulado por API em lotes e relatório em Excel.
- 11 testes e CI com lint (ruff), testes e execução do pipeline.
