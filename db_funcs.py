import sqlite3


def get(table, task="", inftype="*", sqlcities=sqlite3.connect("cities_db.sqlite")):
    crs = sqlcities.cursor()
    print(f"""SELECT {inftype} FROM {table} WHERE {task}""")
    ans = [list(i) for i in crs.execute(f"""SELECT {inftype} FROM {table}{" WHERE " * (task != "") + task}""")]
    print(ans)
    return ans


def insert_into(table, keys, values, sqlcities=sqlite3.connect("data/cities_db.sqlite")):
    crs = sqlcities.cursor()
    executor = f"""INSERT INTO {table}({keys}) VALUES({", ".join(map(str, values))})"""
    print(executor)
    crs.execute(executor)
    sqlcities.commit()


def check(s, type="name", table="cities"):
    a = get(table, f"{type} = {s}")
    return a[0] != []



def create_new_session(user_id, first_city_id, sqlcities=sqlite3.connect("data/cities_db.sqlite")):
    cur = sqlcities.cursor()
    cur.execute(f'''INSERT INTO sessions (user_id, cache) VALUES ({user_id}, {first_city_id})''')
    sqlcities.commit()

def get_all_cities(sqlcities=sqlite3.connect("data/cities_db.sqlite")):
    cur = sqlcities.cursor()
    all_cities = [i[0] for i in cur.execute(f'SELECT (city_id) FROM cities').fetchall()]
    return all_cities

def get_city_by_id(city_id, sqlcities=sqlite3.connect("data/cities_db.sqlite")):
    cur = sqlcities.cursor()
    city = cur.execute(f'''SELECT name FROM cities WHERE city_id = {city_id}''').fetchone()[0]
    return city

#get("cities", "name = 'Москва'", "city_id")