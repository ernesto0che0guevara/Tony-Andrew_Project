import asyncio
import sqlite3

import aiosqlite


async def create_db_pool(path):
    return await aiosqlite.connect(path)

db_pool = asyncio.run(create_db_pool("data/cities_db.sqlite"))


async def get(table, task="", inftype="*", sqlcities=db_pool):
    async with db_pool.execute(f"""SELECT {inftype} FROM {table}{" WHERE " * (task != "") + task}""") as cur:
        ans = await cur.fetchall()
    print(f"""SELECT {inftype} FROM {table} WHERE {task}""")
    print(ans)
    return ans


async def insert_into(table, keys, values, sqlcities=db_pool):
    async with db_pool.execute(f"""INSERT INTO {table}({keys}) VALUES({", ".join(map(str, values))})""") as cur:
        print(cur)
        await cur.commit()


async def check(s, type="name", table="cities"):
    a = await get(table, f"{type} = {s}")
    return a[0] != []



# async def create_new_session(user_id, first_city_id, sqlcities=sqlite3.connect("data/cities_db.sqlite")):
#     async with sqlcities.execute(f'''INSERT INTO sessions (user_id, cache) VALUES ({user_id}, {first_city_id})''') as cur:
#         await cur.commit()
#
# async def get_all_cities(sqlcities=sqlite3.connect("data/cities_db.sqlite")):
#     cur = sqlcities.cursor()
#     all_cities = [i[0] for i in cur.execute(f'SELECT (city_id) FROM cities').fetchall()]
#     return all_cities
#
# async def get_city_by_id(city_id, sqlcities=sqlite3.connect("data/cities_db.sqlite")):
#     cur = sqlcities.cursor()
#     city = cur.execute(f'''SELECT name FROM cities WHERE city_id = {city_id}''').fetchone()[0]
#     return city

#get("cities", "name = 'Москва'", "city_id")