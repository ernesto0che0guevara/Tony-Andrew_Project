from db_funcs import get
from random import randint as rint
import requests
from io import BytesIO
from PIL import Image


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
        arr = [i[0] for i in get("cities", f"name LIKE '{self.ll}*'", "name") if i[0] not in used]
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


a = City("Гавана")
a.findmc()
