/*
  Trava anti-reenvio (T-SQL, SQL Server).
  Roda logo antes do disparo: quem já recebeu mensagem no mesmo canal
  dentro do intervalo mínimo sai da fila, e o motivo fica registrado
  para auditoria e para o cálculo da economia no relatório.
  Nomes de tabelas e colunas são fictícios.
*/
DECLARE @hoje date = CAST(GETDATE() AS date);
DECLARE @intervalo_dias int = 3;
DECLARE @desde date = DATEADD(day, 1 - @intervalo_dias, @hoje);

BEGIN TRANSACTION;

INSERT INTO envio.bloqueio (contato_id, canal, motivo, custo, registrado_em)
SELECT f.contato_id,
       f.canal,
       CONCAT('contatado nos últimos ', @intervalo_dias, ' dias'),
       f.custo,
       SYSDATETIME()
FROM envio.fila AS f
WHERE EXISTS (
    SELECT 1
    FROM envio.historico AS h
    WHERE h.contato_id = f.contato_id
      AND h.canal = f.canal
      AND h.enviado_em >= @desde
);

DELETE f
FROM envio.fila AS f
JOIN envio.bloqueio AS b
  ON b.contato_id = f.contato_id
 AND b.canal = f.canal
WHERE b.registrado_em >= @hoje;

COMMIT TRANSACTION;
