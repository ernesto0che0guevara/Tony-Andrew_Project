from db_funcs import get
from random import randint as rint


class City:
    forbidden_letters = "ЫЬЪЁ".lower()
    lvl1_letters = "КНГШЗХВАПРОЛДЖССМИТБ".lower()
    lvl2_letters = "ЧФЕУЯ".lower() + lvl1_letters
    lvl3_letters = "ЩЙЦЭЮ".lower() + lvl2_letters

    def __init__(self, name):
        inf = get("cities", "city_id, region_id, country_id", f"name = {name}")[0]
        self.id = int(inf[0])
        self.name = name
        self.rid = int(inf[1])
        self.rname = get("regions", "name", f"region_id = {self.rid}")[0][0]
        self.cid = int(inf[2])
        self.cname = get("countries", "name", f"country_id = {self.cid}")[0][0]
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


class Region:
    def __init__(self, name):
        inf = get("regions", "region_id, country_id", f"name = {name}")[0]
        self.id = int(inf[0])
        self.name = name
        self.cid = int(inf[1])
        self.cname = get("countries", "name", f"country_id = {self.cid}")[0][0]

    def getcs(self):
        return [City(i[0]) for i in get("cities", "name", f"region_id = {self.id}")]

    def getC(self):
        return Country(self.cname)


class Country:
    def __init__(self, name):
        inf = get("countries", "country_id", f"name = {name}")[0]
        self.id = int(inf[0])
        self.name = name

    def getrs(self):
        return [Region(i[0]) for i in get("regions", "name", f"country_id = {self.id}")]

    def getcs(self):
        return [i.getcs() for i in self.getrs()]