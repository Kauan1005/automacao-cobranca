# Dos nós KNIME para o código

No trabalho, o pipeline roda em 5 fluxos KNIME. Esta tabela mostra os grupos de nós que eu uso lá e a
função que faz o mesmo papel neste repositório. Os fluxos reais não estão aqui, porque são da empresa.

| Grupo de nós no KNIME | O que faz | Aqui |
|---|---|---|
| DB Connector · DB Query Reader | lê a carteira do dia no SQL Server | `pipeline.ler_csv` (CSV no lugar do banco) |
| String Manipulation · Rule Engine | tira pontuação, recoloca zeros e valida CPF/CNPJ | `documentos.normalizar_documento` |
| String Manipulation · Column Expressions | padroniza telefones e descarta fixos e DDDs inválidos | `telefones.normalizar_celular` |
| Duplicate Row Filter · Sorter | mantém um contrato por pessoa, o de maior atraso | `limpeza.limpar` |
| Rule Engine · Row Splitter | separa por faixa de atraso e escolhe o canal | `segmentacao.segmento_de` / `segmentar` |
| DB SQL Executor | roda a trava em T-SQL antes do envio | `sql/trava_envio.sql` · `trava.aplicar_trava` |
| Chunk Loop Start · JSON Row Combiner · POST Request | monta o JSON e envia em lotes para a API | `disparo.payload_campanha` · `lotes` · `ClienteApi` |
| Python Script | gera o relatório diário de custo e economia | `relatorio.resumo` · `salvar_excel` |

## Por que reescrever em Python

O KNIME é ótimo para a operação: o time enxerga o fluxo e ajusta sem programar. Aqui o objetivo é outro:
mostrar as regras como código testável, com casos de borda (zeros à esquerda, celular sem o 9, contrato
repetido, contato no mesmo canal) cobertos por testes automatizados.
