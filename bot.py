import logging
from telegram.ext import Application, MessageHandler, filters, ConversationHandler, CommandHandler
from config import TOKEN as BOT_TOKEN
import asyncio
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from random import randint as rint

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.ERROR
)

logger = logging.getLogger(__name__)


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new_game", new_game_command))
    application.add_handler(CommandHandler("leaderboards", leaderboards_command))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("rools", rools_message))
    text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, message_processor)
    application.add_handler(text_handler)

    application.run_polling()


async def start(update, context):
    """Отправляет сообщение когда получена команда /start"""
    reply_keyboard = [['/leaderboards'],
                      ['/play']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False)
    user = update.effective_user
    await update.message.reply_html(
        rf"Привет {user.mention_html()}! Я эхо-бот. Напишите мне что-нибудь, и я пришлю это назад!", reply_markup=markup
    )


async def back(update, context):
    await update.message.reply_text(
        "Меню закрыто",
        reply_markup=ReplyKeyboardRemove()
    )


async def message_processor(update, context):
    await error_message(update, context)


async def error_message(update, context):
    await update.message.reply_text("Произошла ошибка:( Мы уже пытаемся её устранить")


async def timer_func(async_func, delay):
    await asyncio.sleep(delay)
    await async_func()


async def play(update, context):
    reply_keyboard = [['/new_game'],
                      ['/continue_game'],
                      ['/new_multiplayer_game']
                      ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False)
    user = update.effective_user
    await update.message.reply_html(
        rf"Привет {user.mention_html()}! Я чат-бот для игры в города. Хотите сыграть?", reply_markup=markup)


async def leaderboards_command(update, context):
    pass


async def new_game_command(update, context):
    pass


async def rools_message(update, context):
    update.message.reply_text("""Правила игры:
    ...
    """)


main()