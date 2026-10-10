"""
Telegram-бот "Орех" — шифрует и расшифровывает текст по подстановочному шифру.

Установка:
    pip install python-telegram-bot --upgrade

Запуск:
    export BOT_TOKEN="твой_токен_от_BotFather"
    python cipher_bot.py

Команды в Telegram:
    /encode <текст>   — зашифровать русский текст
    /decode <текст>   — расшифровать зашифрованный текст
    /alphabet         — показать таблицу шифра
    Просто текст без команды бот попробует расшифровать автоматически,
    если найдёт символы шифра, иначе — зашифрует.

Инлайн-режим (в любом чате, даже где бота нет):
    @имя_бота привет  — появится меню «Шифровать | Расшифровать»,
    выбери пункт — в чат уйдёт готовый результат.
    (Включить: @BotFather -> /setinline)
"""

import os
import re
import logging
import asyncio

from uuid import uuid4

from telegram import (
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)

# --- Таблица шифра (буква -> символ) ---
# Ч, Ш, Ы точно не известны — в присланном ключе их не было.
# Если узнаешь эти символы, впиши их сюда вместо None.
ENCODE_MAP = {
    "А": "7", "Б": "+", "В": "₽", "Г": "2", "Д": "D",
    "Е": "%", "Ж": "/", "З": "!", "И": ":", "Й": "9",
    "К": "#", "Л": "(", "М": ".", "Н": "«", "О": "&",
    "П": "‘", "Р": "b", "С": "ç", "Т": "€", "У": "~",
    "Ф": "^", "Х": "£", "Ц": "m", "Ч": None, "Ш": None,
    "Щ": "¥", "Ъ": "8", "Ы": None, "Ь": ".,.", "Э": "•",
    "Ю": "*", "Я": "3",
}

# Обратная таблица для расшифровки (символ -> буква).
# Строится автоматически из ENCODE_MAP, пропуская None.
DECODE_MAP = {v: k for k, v in ENCODE_MAP.items() if v is not None}

# Токены сортируем по длине по убыванию, чтобы многосимвольный ".,."
# (буква Ь) распознавался раньше одиночной "." (буква М).
DECODE_TOKENS = sorted(DECODE_MAP.keys(), key=len, reverse=True)
DECODE_PATTERN = re.compile("|".join(re.escape(t) for t in DECODE_TOKENS))


def encode(text: str) -> str:
    result = []
    for ch in text.upper():
        if ch in ENCODE_MAP:
            symbol = ENCODE_MAP[ch]
            result.append(symbol if symbol else f"[{ch}?]")  # нет символа — помечаем
        else:
            result.append(ch)  # пробелы, знаки препинания и т.п. оставляем как есть
    return "".join(result)


def decode(text: str) -> str:
    def replace(match: re.Match) -> str:
        return DECODE_MAP[match.group(0)]
    return DECODE_PATTERN.sub(replace, text)


def looks_encoded(text: str) -> bool:
    """Есть ли в тексте хотя бы один символ шифра — считаем, что текст зашифрован."""
    return any(tok in text for tok in DECODE_TOKENS)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я умею шифровать и расшифровывать по таблице «Орех».\n\n"
        "/encode <текст> — зашифровать\n"
        "/decode <текст> — расшифровать\n"
        "/alphabet — показать таблицу шифра\n\n"
        "Можно просто прислать текст без команды — определю сам.\n\n"
        "Инлайн: в любом чате напиши @OpexDecryptBot и текст — выбери «Шифровать» или «Расшифровать»."
    )


async def cmd_encode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Напиши так: /encode привет")
        return
    await update.message.reply_text(encode(text))


async def cmd_decode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Напиши так: /decode 7)&(&")
        return
    await update.message.reply_text(decode(text))


async def cmd_alphabet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = []
    for letter, symbol in ENCODE_MAP.items():
        lines.append(f"{letter} — {symbol if symbol else '???'}")
    await update.message.reply_text("\n".join(lines))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if looks_encoded(text):
        await update.message.reply_text(decode(text))
    else:
        await update.message.reply_text(encode(text))


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = (update.inline_query.query or "").strip()

    if not query:
        # Пустой запрос — подсказка и кнопка перехода в бота.
        await update.inline_query.answer(
            [],
            cache_time=0,
            button=InlineQueryResultsButton(
                text="Введи текст после @имени бота", start_parameter="inline"
            ),
        )
        return

    # Лимит Telegram на длину сообщения — 4096 символов.
    encoded = encode(query)[:4096]
    decoded = decode(query)[:4096]

    enc_result = InlineQueryResultArticle(
        id=str(uuid4()),
        title="🔒 Шифровать",
        description=encoded[:100],
        input_message_content=InputTextMessageContent(encoded),
    )
    dec_result = InlineQueryResultArticle(
        id=str(uuid4()),
        title="🔓 Расшифровать",
        description=decoded[:100],
        input_message_content=InputTextMessageContent(decoded),
    )

    # Если в тексте уже есть символы шифра — «Расшифровать» ставим первым.
    results = [dec_result, enc_result] if looks_encoded(query) else [enc_result, dec_result]
    await update.inline_query.answer(results, cache_time=0, is_personal=False)


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Задай переменную окружения BOT_TOKEN с токеном от @BotFather")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("encode", cmd_encode))
    app.add_handler(CommandHandler("decode", cmd_decode))
    app.add_handler(CommandHandler("alphabet", cmd_alphabet))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(InlineQueryHandler(inline_query))

    # Render Web Service автоматически задаёт RENDER_EXTERNAL_URL и PORT.
    # Если эта переменная есть — запускаемся через webhook (для хостинга).
    # Если её нет — обычный polling (для запуска на своём компьютере).
    base_url = os.environ.get("WEBHOOK_URL") or os.environ.get("RENDER_EXTERNAL_URL")

    if base_url:
        port = int(os.environ.get("PORT", "10000"))
        url_path = token
        full_webhook_url = f"{base_url.rstrip('/')}/{url_path}"
        print(f"Бот запущен через webhook: {full_webhook_url}")

        asyncio.set_event_loop(asyncio.new_event_loop())

        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=url_path,
            webhook_url=full_webhook_url,
        )
    else:
        print("Бот запущен (polling)...")
        app.run_polling()


if __name__ == "__main__":
    main()
