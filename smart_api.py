import time
import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from modules import tools
import config

def run_agent(objective):
    with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            
            tool = tools.Tools()

            context_ds = browser.new_context(locale="ru-RU")
            DeepSeek = context_ds.new_page()
            DeepSeek.goto('https://chat.deepseek.com/sign-in', wait_until='networkidle')
            
            try:
                DeepSeek.fill('input[placeholder*="Номер телефона"]', config.DS_LOGIN)
                time.sleep(1)
                DeepSeek.fill('input[placeholder*="Пароль"]', config.DS_PASS)
                time.sleep(1)
                DeepSeek.click('div[class*="ds-sign-up-form__register-button"]')
                DeepSeek.wait_for_selector('textarea[placeholder*="DeepSeek"]', timeout=30000)
            except Exception as e:
                print(f"Ошибка входа: {e}")
                browser.close()
                return
            
            context_target = browser.new_context()
            target = context_target.new_page()

            target.goto("http://yugprint.ru", wait_until='domcontentloaded')
            found = False
            content = ""
            while not found:
                request = f"""
                                ты - браузерный агент.
                                Задача от пользователя: {objective},
                                текущий адрес страницы: {target.url}
                                в ответе ты можешь вернуть только json одного из двух видов:
                                {{
                                "status": "acting",
                                "reasoning": "Для поиска информации о цене мне нужно найти соответствующие блоки на странице.",
                                "actions": [
                                    {{
                                    "tool": "search_elements",
                                    "parameters": {{
                                        "keywords": ["цена", "купить", "руб"]
                                        "tag":"div"
                                    }}
                                    }}
                                ]
                                }}
                                или
                                {{
                                "status": "found",
                                "answer": [
                                    {{
                                        "your_data":"example_data"
                                    }}
                                ]
                                }}
                                из доступных tools:
                                1. search_elements - выполняет поиск по содержимому тегов. В качаестве parameters:
                                    keywords (обязательный) принимает на вход список слов, по каждому слову выполняется поиск элемента в коде. Слова указывай в инфинитиве и 1 раз, алгоритм в состоянии найти формы этих слов.
                                    tags (обязательно) тут ты можешь указать 1 тег, в котором будут искать выбранные слова.
                                2. full_code - в следующем сообщении будет приведён очищенный html код страницы для анализа, если инструменты не находят нужную информацию. Никаких параметров не принимает.
                                3. go_to - позволяет перейти на страницу, которую ты укажешь. В качаестве parameters:
                                    url (обязательный) адрес страницы, например https://example.com/example_page. Пожалуйста, постарайся игнорировать невалидные адреса страниц.
                                ты можешь указывать несколько действий в одном json ответе.
                                Здесь будет указываться результат прошлого запроса, если только это не начало диалога: {content}
                                """

                initial_count = DeepSeek.locator('div.ds-markdown').count()
                DeepSeek.fill('textarea[placeholder*="DeepSeek"]', request)
                DeepSeek.keyboard.press('Enter')

                DeepSeek.wait_for_function(f'document.querySelectorAll("div.ds-markdown").length > {initial_count}', timeout=90000)

                current_text = ""
                prev_text = ""
                for _ in range(40):
                    if DeepSeek.locator('div.ds-markdown').count() > 0:
                        current_text = DeepSeek.locator('div.ds-markdown').last.inner_text()
                    if current_text == prev_text and len(current_text) > 15: break
                    prev_text = current_text
                    time.sleep(1)
                
                result = tool.search_keywords(target.content(), current_text.lower().split(' '))
                
                json_match = re.search(r'(\{.*\})', current_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                    with open('data.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    if data.get("status") == "found":
                        found = True
                    elif data.get("status") == "acting":
                        for action in data["actions"]:
                            if action["tool"] == "search_elements":
                                found_blocks = tool.search_keywords(target.content(), action["parameters"]["keywords"], action["parameters"]["tag"]) 
                                content = content + "\n" + "".join([str(div) for div in found_blocks])
                            elif action["tool"] == "full_code":
                                content = tool.html_cleaner(target.content())
                            elif action["tool"] == "go_to":
                                content = ""
                                target.goto(action["parameters"]["url"], wait_until='domcontentloaded')
                        

run_agent("Найди мне таблицу с ценами на визитки. Игнорируй все .pdf файлы")