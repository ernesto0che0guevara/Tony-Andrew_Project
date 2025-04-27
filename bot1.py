import logging
from telegram.ext import Application, MessageHandler, filters, ConversationHandler, CommandHandler
from config import TOKEN as BOT_TOKEN
import asyncio
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from random import randint as rint

import wikipedia
import requests
from io import BytesIO
from PIL import Image


# ================================================================
# classes
# ================================================================
class City:
    forbidden_letters = "ЫЬЪЁ".lower()
    lvl1_letters = "КНГШЗХВАПРОЛДЖССМИТБ".lower()
    lvl2_letters = "ЧФЕУЯ".lower() + lvl1_letters
    lvl3_letters = "ЩЙЦЭЮ".lower() + lvl2_letters

    def __init__(self, name):
        inf = get("cities", f"name = '{name}'", "city_id, region_id, country_id")[0]
        self.id = int(inf[0])
        self.name = name
        self.rid = int(inf[1])
        self.rname = get("regions", f"region_id = {self.rid}", "name")[0][0]
        self.cid = int(inf[2])
        self.cname = get("countries", f"country_id = {self.cid}", "name")[0][0]
        self.ll = ""
        self.findll()

    def getr(self):
        return Region(self.rname)

    def getC(self):
        return self.getr().getC()

    def findll(self):
        s = self.name.lower()
        i = -1
        while s[i] in self.forbidden_letters and s[i].isalpha():
            i -= 1
        self.ll = s[i]

    def getca(self, used):
        arr = [i[0] for i in get("cities", f"name LIKE '{self.ll.upper()}%'", "name") if i[0] not in used]
        return arr

    def __str__(self):
        return self.name

    def findmc(self):
        search_api_server = "https://search-maps.yandex.ru/v1/"
        api_key = "dda3ddba-c9ea-4ead-9010-f43fbc15c6e3"
        search_params = {
            "apikey": api_key,
            "text": self.name,
            "lang": "ru_RU",
            "type": "geo"
        }
        response = requests.get(search_api_server, params=search_params)
        json_response = response.json()
        print(json_response)
        city = json_response["features"][0]

        point = city["geometry"]["coordinates"]
        city_point = f"{point[0]},{point[1]}"
        delta = "1"
        apikey = "f3a0fe3a-b07e-4840-a1da-06f18b2ddf13"

        map_params = {
            "spn": ",".join([delta, delta]),
            "apikey": apikey,
            "pt": "{0},pm2dgl".format(city_point)
        }

        map_api_server = "https://static-maps.yandex.ru/v1"
        response = requests.get(map_api_server, params=map_params)
        im = BytesIO(response.content)
        opened_image = Image.open(im)
        opened_image.show()

    def __divmod__(self, other):
        pass

    def __eq__(self, city2):
        return self.ll == city2[0].lower()


class Region:
    def __init__(self, name):
        inf = get("regions", f"name = '{name}'", "region_id, country_id")[0]
        self.id = int(inf[0])
        self.name = name
        self.cid = int(inf[1])
        self.cname = get("countries", f"country_id = {self.cid}", "name")[0][0]

    def getcs(self):
        return [City(i[0]) for i in get("cities", "name", f"region_id = {self.id}")]

    def getC(self):
        return Country(self.cname)


class Country:
    def __init__(self, name):
        inf = get("countries", f"name = '{name}'", "country_id")[0]
        self.id = int(inf[0])
        self.name = name

    def getrs(self):
        return [Region(i[0]) for i in get("regions", "name", f"country_id = {self.id}")]

    def getcs(self):
        return [i.getcs() for i in self.getrs()]

# ================================================================
# db_funcs
# ================================================================
import sqlite3


def get(table, task="", inftype="*", sqlcities=sqlite3.connect("data/cities_db.sqlite")):
    crs = sqlcities.cursor()
    executor = f"""SELECT {inftype} FROM {table}{" WHERE " * (task != "") + task}"""
    print(executor)
    ans = [tuple(i) for i in crs.execute(executor)]
    print(ans)
    return ans


def insert_into(table, keys, values, sqlcities=sqlite3.connect("data/cities_db.sqlite")):
    crs = sqlcities.cursor()
    executor = f"""INSERT INTO {table}({keys}) VALUES({", ".join(map(str, values))})"""
    print(executor)
    crs.execute(executor)
    sqlcities.commit()


def check(s, type="name", table="cities"):
    a = get(table, f"{type} = '{s}'")
    print(a)
    return a != []


# get("cities", "name = 'Москва'", "city_id")

# ================================================================
# game_funcs
# ================================================================
from random import choice as rchoice


def city_handler(cityname, used):
    if not check(cityname, "name", "cities"):
        print(11)
        raise Exception
    city1 = City(cityname)
    vars = city1.getca(used)
    city2 = City(rchoice(vars))
    return str(city2)

# ================================================================

# ================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.ERROR
)

logger = logging.getLogger(__name__)
sessions = {}


class Session:
    def __init__(self, id, uname):
        self.id  = id
        self.name = uname
        self.game = []
        self.in_game = False

    def new_game(self):
        self.game = []
        self.in_game = True

    def stop_game(self):
        self.in_game = False

    def continue_game(self):
        self.in_game = True


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    print('Starting Cities_Game chatbot')

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new_game", new_game_command))
    application.add_handler(CommandHandler("restart", new_game_command))
    # application.add_handler(CommandHandler("leaderboards", leaderboards_command))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("stop", stop_game_command))
    application.add_handler(CommandHandler("continue", continue_game_command))
    application.add_handler(CommandHandler("hint", hint_command))
    # application.add_handler(CommandHandler("rools", rools_message))

    text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, message_processor)
    application.add_handler(text_handler)

    application.run_polling()


async def start(update, context):
    """Отправляет сообщение когда получена команда /start"""
    user = update.effective_user
    sessions[update.message.chat_id] = Session(update.message.chat_id, user)
    button1 = KeyboardButton(text='/play')
    # button2 = KeyboardButton(text='/leaderboards')
    reply_keyboard = [[button1]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_html(
        rf'Привет {user.mention_html()}! Я чат-бот для игры в города' + '\U0001F306', reply_markup=markup
    )


async def back(update, context):
    await update.message.reply_text(
        "Меню закрыто",
        reply_markup=ReplyKeyboardRemove()
    )


async def message_processor(update, context):
    chat_id = update.message.chat_id

    if sessions[chat_id].in_game:
        sess = sessions[chat_id]
        s = update.message.text

        try:
            # await update.message.reply_text("\U00002705")
            if (not sess.game or City(sess.game[-1]) == s) and check(s) and s not in sess.game:
                sess.game.append(s)
                res = city_handler(s, sess.game)
                await city_info(update, context, f"{s}")
                print(res)
                sess.game.append(res)
                print(sess.game)
                await update.message.reply_text(f"Мой ход: {res}")
                await city_info(update, context, f"{res}")
            else:
                if sess.game and City(sess.game[-1]) != s:
                    await update.message.reply_text("Город начинается с неправильной буквы")
                elif not check(s):
                    await update.message.reply_text("Я не знаю такого города")
                elif s in sess.game:
                    await update.message.reply_text("Такой город уже был")
                #raise Exception()
        except Exception as e:
            print(f"{e}")
            await error_message(update, context)
    else:
        # await error_message(update, context)
        await update.message.reply_text("Выберите команду из меню!")
    s = update.message.text


async def city_info(update, context, city_name, is_hint=False):
    print(f"Информация о городе {city_name}:")
    chat_id = update.message.chat_id

    city_images = []
    try:
        wikipedia.set_lang("ru")
        city_images = wikipedia.page(f"Город {city_name} достопримечательность").images
    except Exception:
        print(f"{city_name}: фото в википедии не найдено")
        if is_hint:
            await update.message.reply_text("Попробуйте выбрать подсказку еще раз")

    if city_images:
        city_image = city_images[0]

        print(city_image)
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=city_image)

            if is_hint:
                await update.message.reply_text("Попробуйте угадать это место!")
            else:
                await update.message.reply_text("Интересное о городе!")
        except Exception as e:
            print(f"{city_name}: фото не передано: {e}")
            if is_hint:
                await update.message.reply_text("Попробуйте выбрать подсказку еще раз")

    if not is_hint:
        try:
            wikitext = wikipedia.summary(f"{city_name} Город", sentences=4)
            print(wikitext)
            await update.message.reply_text("Возможно, вы не знали:")
            await update.message.reply_text(wikitext)
        except Exception:
            print(f"{city_name}: информация в википедии не найдена")

    if not is_hint:
        try:
            save_map(city_name)
            await context.bot.send_photo(chat_id=chat_id, photo='data/map.jpg')
        except Exception:
            print("Карта не найдена")


def save_map(city_name):
    search_api_server = "https://search-maps.yandex.ru/v1/"
    api_key = "dda3ddba-c9ea-4ead-9010-f43fbc15c6e3"
    search_params = {
        "apikey": api_key,
        "text": city_name,
        "lang": "ru_RU",
        "type": "geo"
    }
    response = requests.get(search_api_server, params=search_params)
    json_response = response.json()
    # print(json_response)
    city = json_response["features"][0]

    point = city["geometry"]["coordinates"]
    city_point = f"{point[0]},{point[1]}"
    delta = "1"
    apikey = "f3a0fe3a-b07e-4840-a1da-06f18b2ddf13"

    map_params = {
        "spn": ",".join([delta, delta]),
        "apikey": apikey,
        "pt": "{0},pm2dgl".format(city_point)
    }

    map_api_server = "https://static-maps.yandex.ru/v1"
    response = requests.get(map_api_server, params=map_params)
    im = BytesIO(response.content)
    opened_image = Image.open(im)
    rgb_image = opened_image.convert('RGB')
    rgb_image.save("data/map.jpg", 'JPEG')
    # return opened_image


async def error_message(update, context):
    await update.message.reply_text("Произошла ошибка:( Мы уже пытаемся её устранить")


async def timer_func(async_func, delay):
    await asyncio.sleep(delay)
    await async_func()


async def play(update, context):
    chat_id = update.message.chat_id
    u = sessions[chat_id]
    reply_keyboard = [[f'/{"new_game" * (u.game == []) + "restart" * (u.game != [])}'],
                      ['/continue']
                      # ['/new_multiplayer_game']
                      ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
    user = update.effective_user
    await update.message.reply_html(
        rf"Хотите сыграть?", reply_markup=markup)


async def leaderboards_command(update, context):
    pass


async def new_game_command(update, context):
    chat_id = update.message.chat_id
    u = sessions[chat_id]
    u.new_game()
    user = update.effective_user
    reply_keyboard = [['/stop'], ['/hint'], ['/restart']
                      ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_html(
        rf"Ну что, {user.mention_html()}, начинайте!", reply_markup=markup)


async def continue_game_command(update, context):
    chat_id = update.message.chat_id
    u = sessions[chat_id]
    if u.game:
        u.continue_game()
        await update.message.reply_text("Загружаю города...")
    else:
        u.new_game()
        await update.message.reply_text("Нет игры для продолжения...")

    repl = "\n".join(u.game)
    if repl:
        await update.message.reply_text(repl)

    user = update.effective_user
    reply_keyboard = [['/stop'], ['/hint'], ['/restart']
                      ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_html(
        rf"{user.mention_html()}, ваш ход:", reply_markup=markup)


async def hint_command(update, context):
    chat_id = update.message.chat_id
    sess = sessions[chat_id]
    if sess.game:
        last_city = sess.game[-1]
        print(last_city)
        try:
            res = city_handler(sess.game[-1], sess.game)
            await city_info(update, context, f"{res}", True)
        except Exception as e:
            print(f"{e}")
    else:
        await update.message.reply_text("Игра еще не началась...")


async def stop_game_command(update, context):
    chat_id = update.message.chat_id
    u = sessions[chat_id]
    u.stop_game()
    # user = update.effective_user
    button1 = KeyboardButton(text='/play')
    button2 = KeyboardButton(text='/leaderboards')
    reply_keyboard = [[button1]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_html(
        rf"Текущая игра завершена", reply_markup=markup)


async def rools_message(update, context):
    update.message.reply_text("""Правила игры:
    ...
    """)


main()
