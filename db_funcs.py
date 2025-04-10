import sqlite3


def get(table, task="", inftype="*", sqlcities=sqlite3.connect("data/cities_db.sqlite")):
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


#get("cities", "name = 'Москва'", "city_id")