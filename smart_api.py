import time
import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from modules import tools

html = """
<div class="case1">Тут есть слово Програмирование (ошибка в одну букву)</div>
<div class="case2">Здесь_написано_через_подчеркивание_программист</div>
<div class="case3">Сложный-кейс-с-дефисом-программирование</div>
<div class="case4">Просто текст про погоду</div>
<div class="case5">Абсолютно другое слово</div>
"""

words = ["программирование", "программист"]

tool = tools.Tools(threshold=0.7)

result = tool.search_keywords(html, words)

for div in result:
    print(div)