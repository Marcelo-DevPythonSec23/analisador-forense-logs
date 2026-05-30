import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from dados.analysis import AnalysisResult, AnalysisService
from .database import DatabaseManager, SupportDatabaseManager

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

LOGS_DIR = Path("dados/received")
DB_DIR = Path("dados/db")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

analysis_service = AnalysisService()
file_database = DatabaseManager(DB_DIR / "monitoring.db")
support_database = SupportDatabaseManager(DB_DIR / "support_requests.db")


def format_alert_summary(result: "AnalysisResult") -> str:
    if result.total_events == 0:
        return "O arquivo foi salvo, mas não havia eventos válidos para análise."

    # Em resultados de análise, o campo `summary` pode vir na forma
    # {"summary": {...}} ou diretamente como o dicionário interno.
    summary_data = result.summary
    if isinstance(summary_data, dict) and "summary" in summary_data:
        summary_data = summary_data["summary"]

    # Aqui estamos contando os eventos por severidade (ERROR, WARN, INFO) e
    # não apenas os alertas de segurança gerados automaticamente.
    severity_counts = summary_data.get("severity_counts", {})
    critical = severity_counts.get("CRITICAL", 0)
    high = severity_counts.get("HIGH", 0)
    medium = severity_counts.get("MEDIUM", 0)
    low = severity_counts.get("LOW", 0)
    info = severity_counts.get("INFO", 0)
    ok = low + info

    logger.debug(
        "Alert summary computed: total_events=%s total_alerts=%s severity_counts=%s",
        result.total_events,
        result.total_alerts,
        severity_counts,
    )

    return (
        f"📊 Eventos analisados: {result.total_events}\n"
        f"🚨 Alertas gerados: {result.total_alerts}\n"
        f"🔴 Críticos: {critical}\n"
        f"🟠 Altos: {high}\n"
        f"🟡 Médios: {medium}\n"
        f"🔵 Baixos: {low}\n"
        f"ℹ️ Info: {info}\n"
        f"✅ OK: {ok}\n"
        "📌 Relatório de análise disponível no banco de dados."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Bot de Monitoramento Online!\n\n"
        "Use /help para ver os comandos disponíveis.\n"
        "Envie um arquivo .csv para análise forense e CTI.",
        parse_mode="Markdown"
    )
    logger.info(f"Usuário {update.effective_user.id} iniciou o bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "📋 *Comandos Disponíveis*\n\n"
        "/start - Inicia o bot\n"
        "/help - Mostra esta mensagem\n"
        "/status - Verifica status do bot\n"
        "/issue <pedido> | <problema> - Registra um ticket de suporte\n"
        "/files - Lista os arquivos já recebidos\n"
        "/issues - Lista tickets de suporte abertos\n\n"
        "📤 Envie um arquivo .csv para ser processado automaticamente."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")
    logger.info(f"Usuário {update.effective_user.id} solicitou ajuda")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "✅ Bot está *online* e funcionando corretamente!",
        parse_mode="Markdown"
    )
    logger.info(f"Usuário {update.effective_user.id} solicitou status")


async def receber_arquivo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.document:
        await update.message.reply_text("❌ Nenhum arquivo encontrado na mensagem.")
        return

    document = message.document
    filename = document.file_name or "arquivo_recebido"
    extension = Path(filename).suffix.lower()

    if extension not in {".csv", ".log", ".txt"}:
        await message.reply_text(
            "❌ Tipo de arquivo não suportado. Use .csv, .log ou .txt"
        )
        logger.warning(f"Arquivo inválido recebido: {filename} de {update.effective_user.id}")
        return

    file_record_id = file_database.add_file_record(
        filename=filename,
        file_path=str(LOGS_DIR / filename),
        uploader_id=str(update.effective_user.id),
        file_type=extension,
        status="received",
    )

    file_path = LOGS_DIR / filename
    file = await document.get_file()
    await file.download_to_drive(str(file_path))

    await message.reply_text(
        f"✅ Arquivo recebido: *{filename}*\n"
        f"📁 Salvo em: `{file_path}`",
        parse_mode="Markdown"
    )
    logger.info(f"Arquivo recebido e salvo: {filename} (id={file_record_id})")

    if extension == ".csv":
        try:
            result = analysis_service.analyze_file(str(file_path))
            file_database.update_file_analysis(
                file_record_id,
                analysis_summary=result.summary,
                alerts_count=result.total_alerts,
            )
            file_database.add_correlation(
                file_record_id,
                correlation_type="analysis_summary",
                details={
                    "summary": result.summary["summary"],
                    "top_alerts": [alert.alert_id for alert in result.alerts],
                },
            )

            await message.reply_text(
                format_alert_summary(result),
                parse_mode="Markdown"
            )
            logger.info(f"Arquivo analisado: {filename} (id={file_record_id})")
        except Exception as exception:
            logger.error(f"Falha na análise do arquivo {filename}: {exception}")
            await message.reply_text(
                "⚠️ O arquivo foi salvo, mas falhou a análise automática. "
                "Verifique o formato do CSV e tente novamente."
            )
    else:
        await message.reply_text(
            "✅ Arquivo salvo com sucesso. \n"
            "Se for um CSV, ele será analisado automaticamente no próximo envio."
        )


async def issue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    payload = message.text or ""
    parts = payload.split(" ", 1)
    arguments = parts[1] if len(parts) > 1 else ""

    if not arguments:
        await message.reply_text(
            "❌ Use /issue <pedido> | <problema> para registrar seu ticket."
        )
        return

    request_text, separator, problem_description = arguments.partition("|")
    if not separator:
        problem_description = request_text

    request_id = support_database.create_request(
        user_id=str(update.effective_user.id),
        request_text=request_text.strip(),
        problem_description=problem_description.strip(),
    )

    await message.reply_text(
        f"✅ Ticket registrado com sucesso. ID do pedido: *{request_id}*\n"
        "Descreva o problema ou solicitação em detalhes para receber suporte.",
        parse_mode="Markdown"
    )
    logger.info(f"Ticket criado: {request_id} por {update.effective_user.id}")


async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    records = file_database.list_files(limit=10)
    if not records:
        await update.message.reply_text("Nenhum arquivo registrado ainda.")
        return

    lines = [
        "📁 *Arquivos Recebidos Recentes*",
        "```",
    ]
    for row in records:
        lines.append(
            f"#{row['id']} {row['filename']} ({row['file_type']}) - {row['status']} - alertas={row['alerts_count']}"
        )
    lines.append("```")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def list_issues(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    requests = support_database.list_open_requests(limit=10)
    if not requests:
        await update.message.reply_text("Nenhum ticket de suporte aberto no momento.")
        return

    lines = ["📝 *Tickets de Suporte Abertos*", "```"]
    for item in requests:
        lines.append(
            f"#{item['id']} user={item['user_id']} status={item['status']}"
        )
        lines.append(f"  pedido: {item['request_text']}")
        lines.append(f"  problema: {item['problem_description']}")
    lines.append("```")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Não entendi. Use /help para ver os comandos disponíveis ou /issue para registrar um pedido."
    )
    logger.info(f"Mensagem não reconhecida de {update.effective_user.id}")


def main() -> None:
    if not TOKEN:
        logger.error(
            "❌ ERRO: Token do Telegram não configurado! Configure a variável TELEGRAM_TOKEN no arquivo .env"
        )
        raise RuntimeError("TELEGRAM_TOKEN não configurado")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("issue", issue))
    application.add_handler(CommandHandler("files", list_files))
    application.add_handler(CommandHandler("issues", list_issues))
    application.add_handler(MessageHandler(filters.Document.ALL, receber_arquivo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("=" * 80)
    logger.info("🤖 INICIANDO BOT DE MONITORAMENTO")
    logger.info("=" * 80)

    application.run_polling(allowed_updates=Update.ALL_TYPES)
