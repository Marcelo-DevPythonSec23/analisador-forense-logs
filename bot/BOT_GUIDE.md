# 📌 Documentação do Bot de Monitoramento

## Visão Geral

Este documento descreve o funcionamento do bot Telegram, os comandos disponíveis, a integração com o mecanismo de análise e o armazenamento em banco de dados.

## Como iniciar

1. Ative o ambiente virtual:

```bash
source .venv/bin/activate
```

2. Execute o bot:

```bash
python bot/bot.py
```

## Comandos disponíveis

- `/start` - Inicia o bot e exibe mensagem de boas-vindas.
- `/help` - Mostra os comandos disponíveis.
- `/status` - Retorna se o bot está online.
- `/issue <pedido> | <problema>` - Registra um ticket de suporte.
- `/files` - Lista os arquivos recebidos e analisados.
- `/issues` - Lista tickets de suporte abertos.

## Recebimento de arquivos

O bot aceita os arquivos:
- `.csv`
- `.log`
- `.txt`

### Fluxo do arquivo

1. O arquivo é recebido pelo bot.
2. É salvo em `dados/received/`.
3. Se for `.csv`, o arquivo é analisado automaticamente pelo módulo de análise.
4. O resultado é gravado no banco SQLite em `dados/db/monitoring.db`.

## Banco de dados

O bot usa dois bancos SQLite:

- `dados/db/monitoring.db`
  - Tabela `files` para metadados de arquivos recebidos.
  - Tabela `correlations` para dados de correlação e resumo de análise.

- `dados/db/support_requests.db`
  - Tabela `support_requests` para tickets de suporte.

## Integração com análise forense

O bot importa o serviço de análise em `dados/analysis.py`:

- `AnalysisService.analyze_file()`
- `LogParser` para normalizar colunas
- `ForensicAnalyzer` para detectar ameaças
- `CTIAnalyzer` para mapeamento MITRE/CTI

## Observação de severidade

As linhas de log que contenham `nivel` ou `level` são analisadas e mapeadas para severidades:

- `CRITICAL` → `ThreatLevel.CRITICAL`
- `ERROR`, `ERRO`, `failed` → `ThreatLevel.HIGH`
- `WARN`, `WARNING`, `MEDIUM` → `ThreatLevel.MEDIUM`
- `LOW`, `BAIXO` → `ThreatLevel.LOW`
- `INFO` → `ThreatLevel.INFO`

Isso evita que logs de servidor críticos sejam tratados como `INFO`.
