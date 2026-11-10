-- Estrutura mínima usada pela trava (T-SQL). Nomes fictícios.
CREATE SCHEMA envio;
GO

CREATE TABLE envio.historico (
    contato_id  varchar(14)  NOT NULL,
    canal       varchar(10)  NOT NULL,
    enviado_em  datetime2    NOT NULL
);
CREATE INDEX ix_historico_contato ON envio.historico (contato_id, canal, enviado_em);

CREATE TABLE envio.fila (
    contato_id  varchar(14)   NOT NULL,
    canal       varchar(10)   NOT NULL,
    faixa       varchar(12)   NOT NULL,
    custo       decimal(8, 4) NOT NULL
);

CREATE TABLE envio.bloqueio (
    contato_id     varchar(14)   NOT NULL,
    canal          varchar(10)   NOT NULL,
    motivo         varchar(80)   NOT NULL,
    custo          decimal(8, 4) NOT NULL,
    registrado_em  datetime2     NOT NULL
);
