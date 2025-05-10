import json

import requests
from bs4 import BeautifulSoup


response = requests.get('https://ru.wikipedia.org/wiki/Субъекты_Российской_Федерации')

soup = BeautifulSoup(response.text, 'lxml')
data = {}
table = soup.find('table', {'class': 'standard sortable'})
for i in table.find_all('tr'):
    tup = [j.text for j in i.find_all('a')]
    print(tup)
    if len(tup) == 5:
        data[tup[0]] = tup[-2]

with open('provinces.json', 'w', encoding='utf8') as file:
    json.dump(data, file, ensure_ascii=False)