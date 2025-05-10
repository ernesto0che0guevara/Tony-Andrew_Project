import json
import logging
import time

import aiohttp
import aiosqlite
from bs4 import BeautifulSoup
from telegram.ext import Application, MessageHandler, filters, ConversationHandler, CommandHandler, Job


from config import TOKEN as BOT_TOKEN
import asyncio
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from random import randint as rint
import wikipedia
import requests
from io import BytesIO
from PIL import Image




# ================================================================
# db_funcs
# ================================================================
async def create_db_pool(path):
    return await aiosqlite.connect(path)

db_pool = asyncio.run(create_db_pool("data/cities_db.sqlite"))


async def get(table, task="", inftype="*", sqlcities=db_pool):
    async with db_pool.execute(f"""SELECT {inftype} FROM {table}{" WHERE " * (task != "") + task}""") as cur:
        ans = await cur.fetchall()
    # print(ans)
    # print(f"""SELECT {inftype} FROM {table} WHERE {task}""")
    # print(ans)
    return ans


async def insert_into(table, keys, values, sqlcities=db_pool):
    async with db_pool.execute(f"""INSERT INTO {table}({keys}) VALUES({", ".join(map(str, values))})""") as cur:
        # print(cur)
        await cur.commit()


async def check(s, type="name", table="cities"):
    a = await get(table, f"{type} = '{s}'")
    if a == []:
        return False
    return a[0] != []

# ================================================================
# classes
# ================================================================
class City:
    forbidden_letters = "ЫЬЪЁ".lower()
    lvl1_letters = "КНГШЗХВАПРОЛДЖССМИТБ".lower()
    lvl2_letters = "ЧФЕУЯ".lower() + lvl1_letters
    lvl3_letters = "ЩЙЦЭЮ".lower() + lvl2_letters

    async def init(self, name):
        inf = await get("cities", f"name = '{name}'", "city_id, region_id, country_id")
        inf = inf[0]
        self.id = int(inf[0])
        self.name = name
        self.rid = int(inf[1])
        self.rname = await get("regions", f"region_id = {self.rid}", "name")
        self.rname = self.rname[0][0]
        self.cid = int(inf[2])
        self.cname = await get("countries", f"country_id = {self.cid}", "name")
        self.cname = self.cname[0][0]
        s = self.name.lower()
        i = -1
        while s[i] in self.forbidden_letters and s[i].isalpha():
            i -= 1
        self.ll = s[i]


    async def getr(self):
        return Region(self.rname)

    async def getC(self):
        return self.getr().getC()



    async def getca(self, used):
        arr = [i[0] for i in await get("cities", f"name LIKE '{self.ll.upper()}%'", "name") if i[0] not in used]
        return arr

    def __str__(self):
        return self.name

    async def findmc(self):
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
        opened_image.show()

    def __divmod__(self, other):
        pass

    def __eq__(self, city2):
        return self.ll.lower() == city2[0].lower()


class Region:
    async def init(self, name):
        inf = await get("regions", f"name = '{name}'", "region_id, country_id")[0]
        self.id = int(inf[0])
        self.name = name
        self.cid = int(inf[1])
        self.cname = await get("countries", f"country_id = {self.cid}", "name")[0][0]

    async def getcs(self):
        return [City().init(i[0]) for i in await get("cities", "name", f"region_id = {self.id}")]

    def getC(self):
        return Country().init(self.cname)


class Country:
    async def init(self, name):
        inf = await get("countries", f"name = '{name}'", "country_id")
        inf = inf[0]
        self.id = int(inf[0])
        self.name = name

    async def getrs(self):
        return [Region().init(i[0]) for i in await get("regions", "name", f"country_id = {self.id}")]

    async def getcs(self):
        return [await i.getcs() for i in self.getrs()]





# ================================================================
# game_funcs
# ================================================================
from random import choice as rchoice


async def city_handler(cityname, used):
    flag = await check(cityname, "name", "cities")
    if not flag:
        # print(11)
        raise Exception
    city1 = City()
    await city1.init(cityname)
    vars = await city1.getca(used)
    city2 = City()
    await city2.init(rchoice(vars))
    return str(city2)




# ================================================================

# ================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.ERROR
)

logger = logging.getLogger(__name__)
sessions = {}
with open('provinces.json', 'r', encoding='utf8') as file:
    provinces = json.load(file)

class Session:
    async def init(self, id, uname):
        self.id = id
        self.name = uname
        self.game = []
        self.in_game = False
        self.timer = 10

    async def new_game(self):
        self.game = []
        self.in_game = True

    async def stop_game(self):
        self.in_game = False

    async def continue_game(self):
        self.in_game = True

    async def update(self):
        self.timer = 10


def main():
    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()


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
    print('Starting Cities_Game chatbot')
    # application.create_task(check_timers(application))
    application.run_polling()
    # await application.create_task(check_timers(application))


def stop_timer(context, name):
    global timer_range
    timer_range = 20
    timer = context.job_queue.get_jobs_by_name(str(name))
    print(timer)
    for i in timer:
        i.schedule_removal()


async def start_timer(context):
    global timer_range
    timer_range -= 1
    sess = context.job.data['session']
    await context.bot.send_message(context.job.chat_id, text=timer_range)

    reply_keyboard = [[f"/restart"], ['/main_menu']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
    if timer_range == 0:
        await context.bot.send_message(context.job.chat_id, text='ТЫ ПРОИГРАЛ', reply_markup=markup)
        sessions[context.job.chat_id].in_game = False
        async with db_pool.execute(f'UPDATE users SET record = {len(sess)} WHERE id = {context.job.chat_id}') as cur:
            await db_pool.commit()


async def start(update, context):
    """Отправляет сообщение когда получена команда /start"""
    user = update.effective_user
    sessions[update.message.chat_id] = Session()
    await sessions[update.message.chat_id].init(update.message.chat_id, user)
    is_logged_in = await check_user_if_logged_in(update.message.chat_id)
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

timer_range = 20

async def message_processor(update, context):
    chat_id = update.message.chat_id
    if sessions[chat_id].in_game:
        sess = sessions[chat_id]
        s = update.message.text
        # print(s)
        print(f'sess.game - {sess.game}')
        print(s)
        # await update.message.reply_text("\U00002705")

        # print(f'Ход - {sess.game}')
        if (not sess.game or await City().init(sess.game[-1]) == s) and await check(s) and s not in sess.game:
            stop_timer(context, str(chat_id))
            sess.game.append(s)
            res = await city_handler(s, sess.game)
            await city_info(update, context, f"{s}")
            # print(res)
            sess.game.append(res)
            # print(sess.game)
            await update.message.reply_text(f"Мой ход: {res}")
            await city_info(update, context, f"{res}")
            context.job_queue.run_repeating(start_timer, interval=1.0, first=0.0, data=({'session': sess.game}), chat_id=chat_id, name=str(chat_id))

        else:
            city = City()
            await city.init(sess.game[-1])
            print(city, f'Последняя буква {city.ll}')
            if sess.game and city != s:
                await update.message.reply_text("Город начинается с неправильной буквы")
            elif not await check(s):
                # s = await get_province_name(s)
                # s = provinces[s]
                if not await check(s):
                    await update.message.reply_text("Я не знаю такого города")
                else:
                    await update.message.reply_text(f"Я не знаю такого города. Возможно вы имели ввиду {s}?")
            elif s in sess.game:
                await update.message.reply_text("Такой город уже был")
            else:
                stop_timer(context, str(chat_id))
                sess.game.append(s)
                res = await city_handler(s, sess.game)
                await city_info(update, context, f"{s}")
                # print(res)
                sess.game.append(res)
                # print(sess.game)
                await update.message.reply_text(f"Мой ход: {res}")
                await city_info(update, context, f"{res}")
                context.job_queue.run_repeating(start_timer, interval=1.0, first=0.0, data=({'session': sess.game}), chat_id=chat_id, name=str(chat_id))
            # raise Exception()

    else:
        # await error_message(update, context)
        await update.message.reply_text("Выберите команду из меню!")
    s = update.message.text


async def city_info(update, context, city_name, is_hint=False):
    print(city_name)
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://ru.wikipedia.org/wiki/Город {city_name}') as response:
            print(response.status)
            soup = BeautifulSoup(await response.text(), 'lxml')
            main_text = soup.find('p').text.strip()
    await update.message.reply_text(main_text)
    # print(f"Информация о городе {city_name}:")
    # chat_id = update.message.chat_id
    #
    # city_images = []
    # try:
    #     wikipedia.set_lang("ru")
    #     city_images = wikipedia.page(f"Город {city_name} достопримечательность").images
    # except Exception as ex:
    #     print(ex)
    #     print(f"{city_name}: фото в википедии не найдено")
    #     if is_hint:
    #         await update.message.reply_text("Попробуйте выбрать подсказку еще раз")
    #
    # if city_images:
    #     city_image = city_images[0]
    #
    #     print(city_image)
    #     try:
    #         await context.bot.send_photo(chat_id=chat_id, photo=city_image)
    #
    #         if is_hint:
    #             await update.message.reply_text("Попробуйте угадать это место!")
    #         else:
    #             await update.message.reply_text("Интересное о городе!")
    #     except Exception as e:
    #         print(f"{city_name}: фото не передано: {e}")
    #         if is_hint:
    #             await update.message.reply_text("Попробуйте выбрать подсказку еще раз")
    #
    # if not is_hint:
    #     try:
    #         wikitext = wikipedia.summary(f"{city_name} Город", sentences=4)
    #         print(wikitext)
    #         await update.message.reply_text("Возможно, вы не знали:")
    #         await update.message.reply_text(wikitext)
    #     except Exception:
    #         print(f"{city_name}: информация в википедии не найдена")
    #
    # if not is_hint:
    #     try:
    #         await save_map(city_name)
    #         await context.bot.send_photo(chat_id=chat_id, photo='data/map.jpg')
    #     except Exception:
    #         print("Карта не найдена")



async def get_locality_name(geocode):
    server_address = 'http://geocode-maps.yandex.ru/1.x/?'
    api_key = '8013b162-6b42-4997-9691-77b7074026e0'
    geocoder_request = f'{server_address}apikey={api_key}&geocode={geocode}&format=json'
    response = requests.get(geocoder_request).json()
    if response:
        # print(response['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['metaDataProperty']['GeocoderMetaData']['Address']['Components'][-1]['name'])
        return response['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['metaDataProperty']['GeocoderMetaData']['Address']['Components'][-1]['name']


async def get_province_name(geocode):
    server_address = 'http://geocode-maps.yandex.ru/1.x/?'
    api_key = '8013b162-6b42-4997-9691-77b7074026e0'
    geocoder_request = f'{server_address}apikey={api_key}&geocode={geocode}&format=json'
    async with aiohttp.ClientSession() as session:
        async with session.get(geocoder_request) as response:
            response = await response.json()
            if response:
                return response['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['metaDataProperty'][
                    'GeocoderMetaData']['Address']['Components'][-3]['name']



async def save_map(city_name):
    search_api_server = "https://search-maps.yandex.ru/v1/"
    api_key = "dda3ddba-c9ea-4ead-9010-f43fbc15c6e3"
    search_params = {
        "apikey": api_key,
        "text": city_name,
        "lang": "ru_RU",
        "type": "geo"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(search_api_server) as response:
            json_response = await response.json()
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
    await u.new_game()
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
        await u.new_game()
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
        # print(last_city)
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

async def check_user_if_logged_in(user_id):
    user = await get('users', f'id = {user_id}')
    if user != []:
        return True
    else:
        async with db_pool.execute(f"""INSERT INTO users VALUES({user_id}, 'offline')"""):
            await db_pool.commit()
        return False


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()



