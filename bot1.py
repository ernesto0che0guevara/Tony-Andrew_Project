import json
from bs4 import BeautifulSoup
import logging
import aiohttp
import aiosqlite
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


async def create_db_pool(path):
    return await aiosqlite.connect(path)


db_pool = asyncio.run(create_db_pool("data/cities_db.sqlite"))


async def get(table, task="", inftype="*", sqlcities=db_pool):
    async with db_pool.execute(f"""SELECT {inftype} FROM {table}{" WHERE " * (task != "") + task}""") as cur:
        ans = [list(i) for i in await cur.fetchall()]
    print(f"""SELECT {inftype} FROM {table} WHERE {task}""")
    print(ans)
    return ans


async def set(table, task, inftypes, values, type="str" , sqlcities=db_pool):
    if type == "str":
        executor = f"""UPDATE {table}\nSET {", ".join([inftypes[i] + " = " + f"'{values[i]}'" for i in range(len(inftypes))])}\nWHERE {task}"""
    else:
        executor = f"""UPDATE {table}\nSET {", ".join([inftypes[i] + " = " + f"{values[i]}" for i in range(len(inftypes))])}\nWHERE {task}"""
    print(executor)
    async with db_pool.execute(executor) as cur:
        await db_pool.commit()


async def insert_into(table, keys, values, sqlcities=db_pool):
    executor = f"""INSERT INTO {table} ({keys}) VALUES ({values})"""
    print(executor)
    async with db_pool.execute(executor) as cur:
        await db_pool.commit()


async def delete(table, task="", sqlcities=db_pool):
    async with db_pool.execute(f"""DELETE FROM {table}{" WHERE " * (task != "") + task}""") as cur:
        print(f"""DELETE FROM {table} WHERE {task}""")
        await db_pool.commit()


async def check(s, type="name", table="cities"):
    a = await get(table, f"{type} = '{s}'")
    return a != []


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
sep = "/"


from random import choice as rchoice


async def get_sess(id):
    return (await get("users", f"uname = '{id}'"))[0]


async def get_mp_sess(id):
    return (await get("mp_sessions", f"sessid = '{id}'"))[0]


async def create_new_sess(id, chat_id):
    await insert_into("users", "uname, chatid, curmpid, status, wins", f"'{id}', {chat_id}, '/', 'ia', 0")


async def create_new_mp_sess(id):
    await insert_into("mp_sessions", "sessid, curtid", f"'{id}', 0")


async def change_sess(id, params, values):
    await set("users", f"uname = '{id}'", params, values)


async def change_mp_sess(id, param, value, type="str"):
    await set("mp_sessions", f"sessid = '{id}'", param, value, type=type)


async def check_sess(id):
    return id not in [i[0] for i in await get("users", inftype="uname")]


async def check_mp_sess(id):
    return id in [i[0] for i in await get("mp_sessions", inftype="sessid")]


async def update_mp_sess(id):
    lst1 = [i[0] for i in await get("users", f"curmpid = '{id}'", "uname")]
    new_id = sep.join(lst1)
    await set("mp_sessions", f"sessid = '{id}'", ["sessid"], [new_id])
    await set("game_cities", f"sessid = '{id}'", ["sessid"], [new_id])
    await set("users", f"curmpid = '{id}'", ["curmpid"], [new_id])
    return new_id


async def get_act_players(sessid):
    lst1 = [i[0] for i in await get("users", f"curmpid = '{id}'", "uname")]
    return lst1


async def get_cities(id):
    return [i[0] for i in await get("game_cities", f"sessid = '{id}'", "city")]


async def add_city(name, id):
    await insert_into("game_cities", "sessid, city", f"'{id}', '{name}'")


async def get_chat_id(id):
    return (await get("users", f"uname = '{id}'", "chatid"))[0][0]


async def add_user_to_mp_sess(id, mp_id):
    await set("users", f"uname = '{id}'", ["curmpid", "status"], [mp_id, "mp"])


async def city_handler(cityname, used):
    flag = await check(cityname, "name", "cities")
    if not flag:
        print(11)
        raise Exception
    city1 = City()
    await city1.init(cityname)
    vars = await city1.getca(used)
    city2 = City()
    await city2.init(rchoice(vars))
    return str(city2)


async def city_info(update, context, city_name, is_hint=False):
    print(city_name)
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://ru.wikipedia.org/wiki/{city_name}') as response:
            assert response.status == 200
            soup = BeautifulSoup(await response.text(), 'lxml')
            main_text = soup.find('p').text.strip()
    await update.message.reply_text(main_text)

# ================================================================

# ================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.ERROR
)

logger = logging.getLogger(__name__)
stmp, plmp, plsp, chmp, remp = range(5)


# ================================================================

# ================================================================

button1 = KeyboardButton(text='/play_singleplayer_game')
button2 = KeyboardButton(text='/play_multiplayer_game')
button3 = KeyboardButton(text='/leaderboards')
button4 = KeyboardButton(text='/rules')
reply_keyboard = [[button1, button2], [button3], [button4]]
start_markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
del_markup = ReplyKeyboardRemove()
reply_keyboard = [['/new_multiplayer_game'],
                      ['/continue_multiplayer_game'],
                      ]
stmp_markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)


# ================================================================

# ================================================================
rules = open("rules.txt", encoding="utf8", mode="r").read()


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    print('Starting Cities_Game chatbot')

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cl", cl_bd))
    #application.add_handler(CommandHandler("join_multiplayer_game", join_mp_game_command))
    application.add_handler(CommandHandler("continue_multiplayer_game", continue_mp_game_command))
    application.add_handler(CommandHandler("leaderboards", leaderboards_command))
    application.add_handler(CommandHandler("rules", rules_message))
    application.add_handler(CommandHandler("play_singleplayer_game", play_sp))
    application.add_handler(CommandHandler("play_multiplayer_game", play_mp))
    mp_handler = ConversationHandler(
        entry_points=[CommandHandler('new_multiplayer_game', new_mp_game_command),
                      CommandHandler('load_multiplayer_game', load_mp_game_command),
                      CommandHandler('join_multiplayer_game', join_mp_game_command)],
        states={
            stmp: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_mp)],
            plmp: [MessageHandler(filters.TEXT & ~filters.COMMAND, mp_play)],
        },
        fallbacks=[CommandHandler('end_match', end_mp),
                   CommandHandler('leave_match', leave_mp),
                   CommandHandler('surrender', surrender_mp)],
    )
    sp_handler = ConversationHandler(
        entry_points=[CommandHandler('new_singleplayer_game', new_sp_game_command),
                      CommandHandler('restart_singleplayer_game', new_sp_game_command),
                      CommandHandler("continue_singleplayer_game", continue_sp_game_command)],
        states={
            plsp: [MessageHandler(filters.TEXT & ~filters.COMMAND, sp_play)],
        },
        fallbacks=[CommandHandler('stop', stop_game_command)],
    )
    application.add_handler(mp_handler)
    application.add_handler(sp_handler)
    application.add_handler(CommandHandler("hint", hint_command))
    application.add_handler(CommandHandler("cancel", cancel))
    # application.add_handler(CommandHandler("rules", rules_message))

    # text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, message_processor)
    # application.add_handler(text_handler)

    application.run_polling()


async def start(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    if await check_sess(user):
        await create_new_sess(user, chat_id)
    await update.message.reply_html(
        rf'Привет {update.effective_user.mention_html()}! Я чат-бот для игры в города' + '\U0001F306', reply_markup=start_markup
    )


async def back(update, context):
    await update.message.reply_text(
        "Меню закрыто",
        reply_markup=del_markup
    )

'''
async def message_processor(update, context):
    chat_id = update.message.chat_id

    if chat_id in sessions and sessions[chat_id].in_game:
        sess = sessions[chat_id]
        s = await get_locality_name(update.message.text)
        print(s)

        # await update.message.reply_text("\U00002705")
        if (not sess.game or await City().init(sess.game[-1]) == s) and await check(s) and s not in sess.game:
            sess.game.append(s)
            res = await city_handler(s, sess.game)
            await city_info(update, context, f"{s}")
            print(res)
            sess.game.append(res)
            print(sess.game)
            await update.message.reply_text(f"Мой ход: {res}")
            await city_info(update, context, f"{res}")
        else:
            if sess.game and await City().init(sess.game[-1]) != s:
                await update.message.reply_text("Город начинается с неправильной буквы")
            elif not await check(s):
                s = await get_province_name(s)
                if not await check(s):
                    await update.message.reply_text("Я не знаю такого города")
                else:
                    await update.message.reply_text(f"Я не знаю такого города. Возможно вы имели ввиду {s}?")
            if s in sess.game:
                await update.message.reply_text("Этот город уже был")
            # raise Exception()

    elif chat_id in sessions and sessions[chat_id].in_mp_game:
        mpgame = mp_sessions[sessions[chat_id].cur_mp_game_id]
        if chat_id == mpgame["queue"][mpgame["turn"]]:
            s = update.message.text
            if (not mpgame["cities"] or await City().init(mpgame["cities"][-1]) == s) and await check(s) and s not in mpgame["cities"]:
                mpgame["cities"].append(s)
                for i in mpgame["queue"]:
                    if i != chat_id:
                        await context.bot.send_message(text=f"Ход {sessions[chat_id].name}: {s}", chat_id=i)
                mpgame["turn"] = (mpgame["turn"] + 1) % len(mpgame["queue"])
                await context.bot.send_message(text="Ваш ход:", chat_id=mpgame["queue"][mpgame["turn"]])
            else:
                if mpgame["cities"] and await City().init(mpgame["cities"][-1]) != s:
                    await update.message.reply_text("Город начинается с неправильной буквы")
                elif not await check(s):
                    s = await get_province_name(s)
                    if not await check(s):
                        await update.message.reply_text("Я не знаю такого города")
                    else:
                        await update.message.reply_text(f"Я не знаю такого города. Возможно вы имели ввиду {s}?")
                if s in mpgame["cities"]:
                    await update.message.reply_text("Этот город уже был")
                # raise Exception()
        else:
            await update.message.reply_text("Дождитесь своего хода!")

    else:
        # await error_message(update, context)
        await update.message.reply_text("Выберите команду из меню!")
    s = update.message.text

'''


async def city_info(update, context, city_name, is_hint=False):
    print(f"Информация о городе {city_name}:")
    chat_id = update.message.chat_id

    city_images = []
    try:
        wikipedia.set_lang("ru")
        city_images = wikipedia.page(f"Город {city_name} достопримечательность").images
    except Exception as ex:
        print(ex)
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
            await save_map(city_name)
            await context.bot.send_photo(chat_id=chat_id, photo='data/map.jpg')
        except Exception:
            print("Карта не найдена")


async def get_locality_name(geocode):
    server_address = 'http://geocode-maps.yandex.ru/1.x/?'
    api_key = '8013b162-6b42-4997-9691-77b7074026e0'
    geocoder_request = f'{server_address}apikey={api_key}&geocode={geocode}&format=json'
    response = requests.get(geocoder_request).json()
    if response:
        print(response['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['metaDataProperty']['GeocoderMetaData']['Address']['Components'][-1]['name'])
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

    print('map_params', map_params)

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


async def play_sp(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    u = await get_sess(user)
    cities = await get_cities(user)
    reply_keyboard = [[f'/{"new_singleplayer_game" * (cities == []) + "restart_singleplayer_game" * (cities != [])}'],
                      ['/continue_singleplayer_game'],
                      ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    user = update.effective_user
    await update.message.reply_html(
        rf"Хотите сыграть?", reply_markup=markup)


async def play_mp(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    u = await get_sess(user)
    cities = await get_cities(user)

    user = update.effective_user
    await update.message.reply_html(
        rf"Хотите сыграть?", reply_markup=stmp_markup)


async def start_mp(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    u = await get_sess(user)
    s = update.message.text
    if not await check_p_l(s):
        await update.message.reply_text("Некорректный формат ввода!\nВведите ники игроков через пробел")
        return stmp
    else:
        await update.message.reply_text("Отправляю запросы пользователям...")
        lst = await check_p_l(s)
        first_id = sep.join([user] + lst)
        reply_keyboard = [[f'/join_multiplayer_game {first_id}'],
                          [f'/cancel {first_id}'],
                          ]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await add_user_to_mp_sess(user, first_id)
        for i in lst:
            if await check_sess(i):
                await update.message.reply_text(f"{i} ещё не запускал бот")
            elif i != user:
                print(331)
                chid = await get_chat_id(i)
                await change_sess(i, ["status"], ["pending"])
                await context.bot.send_message(
                    text=f"{user} приглашает вас сыграть в игру. Хотите присоединиться?", chat_id=chid, reply_markup=markup)
                print(332)
        return plmp


async def end_mp(update, context):
    user = update.message.from_user.username
    mp_sess_id = (await get_sess(user))[2]
    if (await get_sess(user))[3] == "mp":
        mp_sess_lst = list(mp_sess_id.split(sep))
        reply_keyboard = [["/leave_match"]]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        for us in mp_sess_lst:
            if us != user and (await get_sess(us))[3] == "mp":
                await context.bot.send_message(text="Сессия остановлена. Инициализатор завершил сессию. Нажмите, чтобы выйти из сессии:",
                                                chat_id=await get_chat_id(us), reply_markup=markup)
            elif (await get_sess(us))[3] == "mp":
                await context.bot.send_message(text="Сессия остановлена.",
                                                chat_id=await get_chat_id(us), reply_markup=start_markup)
    else:
        await update.message.reply_text("Сессия остановлена")
    await change_sess(user, ["status", "curmpid"], ["ia", ""])
    return ConversationHandler.END


async def leave_mp(update, context):
    user = update.message.from_user.username
    mp_sess_id = (await get_sess(user))[2]
    if (await get_sess(user))[3] == "mp":
        mp_sess_lst = list(mp_sess_id.split(sep))
        reply_keyboard1 = [["/leave_match"]]
        reply_keyboard2 = [["/end_match"]]
        markup1 = ReplyKeyboardMarkup(reply_keyboard1, one_time_keyboard=True, resize_keyboard=True)
        markup2 = ReplyKeyboardMarkup(reply_keyboard2, one_time_keyboard=True, resize_keyboard=True)
        initer = mp_sess_lst[0]
        for us in mp_sess_lst:
            if us != user and us != initer and (await get_sess(us))[3] == "mp":
                await context.bot.send_message(text=f"Сессия остановлена. @{user} вышел из игры. Нажмите, чтобы выйти из сессии:",
                                                chat_id=await get_chat_id(us), reply_markup=markup1)
            elif us == user and (await get_sess(us))[3] == "mp":
                await context.bot.send_message(text=f"Сессия остановлена. Вы вышли из этой игры.",
                                                chat_id=await get_chat_id(us), reply_markup=start_markup)
            elif (await get_sess(us))[3] == "mp":
                await context.bot.send_message(text=f"Сессия остановлена. @{user} вышел из игры. Нажмите, чтобы выйти из сессии:",
                                                chat_id=await get_chat_id(us), reply_markup=markup2)
    else:
        await update.message.reply_text("Сессия остановлена")
    await change_sess(user, ["status", "curmpid"], ["ia", ""])
    return ConversationHandler.END


async def surrender_mp(update, context):
    user = update.message.from_user.username
    sessid = (await get_sess(user))[2]
    mp_sess_lst = list(sessid.split(sep))
    await change_sess(user, ["status"], ["sd"])
    stst = [i for i in mp_sess_lst if (await get_sess(i))[3] == "mp"]

    if len(stst) > 1:
        for us in mp_sess_lst:
            if us != user:
                await context.bot.send_message(text=f"@{user} сдал(ся/ась)", chat_id=await get_chat_id(us),
                                               reply_markup=start_markup)
        curtid = int((await get_mp_sess(sessid))[1])
        n = len(mp_sess_lst)
        while (await get_sess(mp_sess_lst[curtid]))[3] == "sd":
            curtid = (curtid + 1) % n
        await change_mp_sess(sessid, ["curtid"], [curtid], type="int")
        await context.bot.send_message(text="Ваш ход:", chat_id=mp_sess_lst[curtid])
    else:
        initer = mp_sess_lst[0]
        winner = stst[0]
        reply_keyboard = [[f"/{'leave' * (winner != initer) + 'end' * (winner == initer)}_match"]]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await delete("mp_sessions", f"sessid = '{sessid}'")
        await delete("game_cities", f"sessid = '{sessid}'")
        for us in mp_sess_lst:
            await change_sess(us, ["curmpid", "status"], ["", "ia"])
            if us != winner and us != user:
                await context.bot.send_message(
                    text=f"@{user} сдал(ся/ась).\nИгра закончена!\n@{winner} объявляется победителем! \U0001F3C6",
                    chat_id=await get_chat_id(us), reply_markup=start_markup)
            elif us == user:
                await context.bot.send_message(
                    text=f"Игра закончена!\n@{winner} объявляется победителем! \U0001F3C6",
                    chat_id=await get_chat_id(us), reply_markup=start_markup)
            else:
                await context.bot.send_message(
                    text=f"Игра закончена!\nВы победили! \U0001F3C6\nНажмите, чтобы выйти из сессии:",
                    chat_id=await get_chat_id(us), reply_markup=markup)
        await change_sess(winner, ["wins"], [int((await get_sess(winner))[4]) + 1])
    return ConversationHandler.END


async def join_mp_game_command(update, context):
    user = update.message.from_user.username
    await add_user_to_mp_sess(user, context.args[0])
    await update.message.reply_text(f"Вы присоединились к сессии {context.args[0]}")
    print(1)
    first_id = str(context.args[0])
    lst = list(first_id.split(sep))
    print(lst)
    word = "загружена"
    if not await check_pl(lst[1:]):
        print(2)
        if not await check_mp_sess(first_id):
            word = "создана"
            await create_new_mp_sess(first_id)
        print(3)
        await change_sess(user, ["curmpid"], [first_id])
        print(4)
        second_id = await update_mp_sess(first_id)
        lst = list(second_id.split(sep))
        print(lst)
        print(5)
        chid = await get_chat_id(lst[(await get_mp_sess(second_id))[1]])
        reply_keyboard1 = [['/leave_match'], ["/surrender"]]
        reply_keyboard2 = [['/end_match'], ["/surrender"]]
        print(61)
        listo = "\n".join([f"- @{i}" for i in lst])
        print(listo)
        mp_sess = await get_mp_sess((await get_sess(user))[2])
        cities_listo = "\n".join([f"- {i}" for i in await get_cities(second_id)])
        cities_str = ""
        if cities_listo:
            cities_str = f"\nНазванные города:\n{cities_listo}"
        initer = lst[0]
        for u in lst:
            if u == initer:
                markup = ReplyKeyboardMarkup(reply_keyboard2, one_time_keyboard=False, resize_keyboard=True)
            else:
                markup = ReplyKeyboardMarkup(reply_keyboard1, one_time_keyboard=False, resize_keyboard=True)
            await context.bot.send_message(text=f"Сессия {word}. Игроки:\n{listo}{cities_str}",
                                            chat_id=await get_chat_id(u), reply_markup=markup)
        await context.bot.send_message(text="Ваш ход:", chat_id=chid)
    else:
        print(62)
        # await context.bot.send_message(text="Сессия не создана.\nСлишком мало людей!", chat_id=chid)
    return plmp


async def continue_mp_game_command(update, context):
    user = update.message.from_user.username
    lst = await get("mp_sessions", inftype="sessid")
    lst = [i[0] for i in lst if i[0].find(user) == 0]
    reply_keyboard = [[f'/load_multiplayer_game {i}'] for i in lst] + [["/back"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Выберите одну из ваших сохранённых сессий:", reply_markup=markup)


async def load_mp_game_command(update, context):
    print(111111111)
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    u = await get_sess(user)
    print(111111111)
    await update.message.reply_text("Отправляю запросы пользователям...")
    first_id = context.args[0]
    lst = list(first_id.split(sep))
    reply_keyboard = [[f'/join_multiplayer_game {first_id}'],
                      [f'/cancel {first_id}'],
                      ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    fnllst = []
    await add_user_to_mp_sess(user, first_id)
    for i in lst:
        if await check_sess(i):
            await update.message.reply_text(f"{i} ещё не запускал бот")
        elif i != user:
            fnllst.append(i)
            print(331)
            chid = await get_chat_id(i)
            await change_sess(i, ["status"], ["pending"])
            await context.bot.send_message(
                text=f"{user} приглашает вас сыграть в игру. Хотите присоединиться?", chat_id=chid, reply_markup=markup)
            print(332)
    return plmp


async def sp_play(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    u = await get_sess(user)
    cities = await get_cities(user)
    # s = await get_locality_name(update.message.text)
    s = update.message.text.lower().capitalize()
    print(s)
    print(cities)
    # await update.message.reply_text("\U00002705")
    if not cities or (await check(s) and await get_ll(cities[-1]) == s[0].lower() and s not in cities):
        await update.message.reply_text("Зачтено\U00002714")
        await add_city(s.lower().capitalize(), user)
        res = await city_handler(s, cities)
        await city_info(update, context, f"{s}")
        print(res)
        await add_city(res.lower().capitalize(), user)
        print(cities)
        await update.message.reply_text(f"Мой ход: {res}")
        await city_info(update, context, f"{res}")
    else:
        if await get_ll(cities[-1]) != s[0].lower():
            await update.message.reply_text("Город начинается с неправильной буквы!")
        elif not await check(s):
            # s = await get_province_name(s)
            await update.message.reply_text("Такого города нет в моей базе данных!")
            # if await check(s):
                # await update.message.reply_text(f"Возможно вы имели ввиду {s}?")
        if s in cities:
            await update.message.reply_text("Такой город уже был!")


async def mp_play(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    u = await get_sess(user)
    cities = await get_cities(u[2])
    print(cities)
    mpsess = await get_mp_sess(u[2])
    print(f"USER: {user}")
    queue = list(mpsess[0].split(sep))
    req = update.message.text.lower().capitalize()
    print(req)
    if queue[int(mpsess[1])] == u[0]:
        # if not cities or (await get_ll(cities[-1]) == req[0].lower() and req not in cities):
        if not cities or (await check(req) and await get_ll(cities[-1]) == req[0].lower() and req not in cities):
            await add_city(req.capitalize(), mpsess[0])
            for i in queue:
                if i != user:
                    chid = await get_chat_id(i)
                    await context.bot.send_message(text=f"Ход @{user}: {req.capitalize()}", chat_id=chid)
            curtid = int(mpsess[1])
            curtid = (curtid + 1) % (u[2].count(sep) + 1)
            while (await get_sess(queue[curtid]))[3] == "sd":
                curtid = (curtid + 1) % (u[2].count(sep) + 1)
            await change_mp_sess(u[2], ["curtid"], [curtid], type="int")
            await context.bot.send_message(text="Ваш ход:", chat_id=(await get_sess(queue[(await get_mp_sess(u[2]))[1]]))[1])
            await update.message.reply_text("Зачтено\U00002714")
        elif not await check(req):
            await update.message.reply_text("Такого города нет в моей базе данных!")
        elif get_ll(cities[-1]) != req[0].lower():
            await update.message.reply_text("Город начинается с неправильной буквы!")
        elif req in cities:
            await update.message.reply_text("Такой город уже был!")
    else:
        await update.message.reply_text("Дождитесь своей очереди!")
    return plmp


async def leaderboards_command(update, context):
    user = update.message.from_user.username
    wins = (await get_sess(user))[4]
    best = sorted([[i[0], int(i[1])] for i in await get("users", inftype="uname, wins")], key=lambda x: x[1], reverse=True)[:5]
    medals = ["\U0001F947", "\U0001F948", "\U0001F949", "\U0001F3C5", "\U0001F3C5"]
    numbers = ["I", "II", "III", "IV", "V"]
    best_text = ""
    for i in range(5):
        if len(best) > i:
            s = f"{medals[i]} {numbers[i]} место: @{best[i][0]} - {best[i][1]} побед;\n"
        else:
            s = f"{medals[i]} {numbers[i]} место: . . . . . . . . ;\n"
        best_text += s
    best_text += "< . . . . . . . . >\n"
    total = [int(i[0]) for i in await get("users", inftype="wins")]
    place = total.index(wins) + 1

    text = f"Ваша статистика\U0001F4CA:\nТоп 5 игроков:\n\n{best_text}Вы находитесь на" \
           f" {place}-м месте.\nВсего побед в многопользовательских матчах: {wins}"
    await update.message.reply_text(text)


async def new_sp_game_command(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    u = await get_sess(user)
    await change_sess(user, ["status"], ["sp"])
    await delete("game_cities", f"sessid = '{user}'")
    user = update.effective_user
    reply_keyboard = [['/stop']
                      ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_html(
        rf"Ну что, {user.mention_html()}, начинайте!", reply_markup=markup)
    return plsp


async def continue_sp_game_command(update, context):
    user = update.message.from_user
    u = await get_sess(user.username)
    cities = await get_cities(user.username)
    if cities:
        await change_sess(user.username, ["status"], ["sp"])
        await update.message.reply_text("Загружаю города...")
        await update.message.reply_text("\n".join(cities))
    else:
        await update.message.reply_text("Нет игры для продолжения...")
    reply_keyboard = [['/stop'], ['/hint']
                      ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_html(
        rf"{user.mention_html()}, ваш ход:", reply_markup=markup)
    return plsp


async def hint_command(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    sess = await get_sess(user)
    cities = await get_cities(user)
    if cities:
        last_city = cities[-1]
        print(last_city)
        try:
            res = city_handler(cities[-1], cities)
            await city_info(update, context, f"{res}", True)
        except Exception as e:
            print(f"{e}")
    else:
        await update.message.reply_text("Игра еще не началась...")


async def stop_game_command(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    u = await get_sess(user)
    await change_sess(user, ["status"], ["ia"])
    await update.message.reply_html(
        rf"Текущая игра приостановлена", reply_markup=start_markup)
    return ConversationHandler.END


async def new_mp_game_command(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user.username
    u = await get_sess(user)
    await change_sess(user, ["status"], ["mp"])
    await update.message.reply_text("Отправьте ники игроков через пробел:")
    return stmp


async def cancel(update, context):
    user = update.message.from_user
    logger.info("Пользователь %s отменил разговор.", user.first_name)
    await change_sess(user.username, ["status", "curmpid"], ["ia", ""])
    await update.message.reply_text(
        text="Вы отказались от присоединения к игре",
        reply_markup=del_markup
    )
    user = user.username
    print(1)
    first_id = str(context.args[0])
    lst = list(first_id.split(sep))
    initer = lst[0]
    print(lst)
    word = "загружена"
    if len(await get_act_players(first_id)) > 1:
        print(2)
        if not await check_mp_sess(first_id):
            word = "создана"
            await create_new_mp_sess(first_id)
        print(4)
        second_id = await update_mp_sess(first_id)
        lst = list(second_id.split(sep))
        print(lst)
        print(5)
        chid = await get_chat_id(lst[(await get_mp_sess(second_id))[1]])
        reply_keyboard1 = [['/leave_match'], ["/surrender"]]
        reply_keyboard2 = [['/end_match'], ["/surrender"]]
        print(61)
        listo = "\n".join([f"- @{i}" for i in lst])
        print(listo)
        cities_listo = "\n".join([f"- {i}" for i in await get_cities(second_id)])
        cities_str = ""
        if cities_listo:
            cities_str = f"\nНазванные города:\n{cities_listo}"
        initer = lst[0]
        for u in lst:
            if u == initer:
                markup = ReplyKeyboardMarkup(reply_keyboard2, one_time_keyboard=False, resize_keyboard=True)
            else:
                markup = ReplyKeyboardMarkup(reply_keyboard1, one_time_keyboard=False, resize_keyboard=True)
            await context.bot.send_message(text=f"Сессия {word}. Игроки:\n{listo}{cities_str}",
                                            chat_id=await get_chat_id(u), reply_markup=markup)
        await context.bot.send_message(text="Ваш ход:", chat_id=chid)
    else:
        reply_keyboard = [["/end_match"]]
        print(62)
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(text="Сессия не создана.\nСлишком мало людей!\nНажмите, чтобы выйти из сессии:",
                                       chat_id=await get_chat_id(initer), reply_markup=markup)


async def check_p_l(s):
    print(f"Проверяю '{s}'")
    s = s.strip(" ")
    s = list(s.split())
    ans = []
    if all(i[0] == "@" for i in s):
        ans = [i[1:] for i in s]
    print(ans)
    return ans


async def check_pl(lst):
    # lst = [(await get_sess(username))[3] for username in lst if await check_sess(username)]
    lst = [(await get_sess(username))[3] for username in lst]
    lst2 = [i == "pending" for i in lst]
    ans = sum(lst2) != 0
    print("Проверяю список:", lst, ans)
    return ans


async def rules_message(update, context):
    await update.message.reply_text(rules)


async def cl_bd(update, context):
    await delete("mp_sessions")
    await delete("game_cities")
    await set("users", "uname = uname", inftypes=["curmpid", "status"], values=["None", "ia"])
    await update.message.reply_text("Database cleared!")


async def get_ll(s):
    forbidden_letters = "ЫЬЪЁ".lower()
    i = -1
    while s[i].lower() in forbidden_letters and s[i].isalpha():
        i -= 1
    return s[i].lower()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()
