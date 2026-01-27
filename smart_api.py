import time
import json
import re
import sys
import io
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from modules import tools
from modules import mail

try:
    import config
except ImportError:
    with open("config.py", "w", encoding="utf-8") as f:
        f.write('DS_LOGIN = "YOUR_PHONE_OR_EMAIL"\nDS_PASS = "YOUR_PASSWORD"\n')
    import config

def run_agent(objective, starter_url):
    start_time_global = time.time()
    with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            
            tool = tools.Tools()
            mail_tool = mail.MailClient()

            context_ds = browser.new_context(locale="ru-RU")
            DeepSeek = context_ds.new_page()
            
            try:
                DeepSeek.goto('https://chat.deepseek.com/sign-in', wait_until='networkidle', timeout=60000)
                
                if "YOUR_PHONE" in config.DS_LOGIN or "YOUR_PASS" in config.DS_PASS:
                    DeepSeek.wait_for_selector('textarea[id*="chat-input"], textarea[placeholder*="DeepSeek"]', timeout=120000)
                else:
                    if DeepSeek.locator('input[placeholder*="Номер телефона"], input[placeholder*="Email"]').count() > 0:
                        DeepSeek.fill('input[placeholder*="Номер телефона"], input[placeholder*="Email"]', config.DS_LOGIN)
                        time.sleep(1)
                        DeepSeek.fill('input[type="password"]', config.DS_PASS)
                        time.sleep(1)
                        DeepSeek.get_by_role("button", name=re.compile(r"Войти|Log In", re.I)).click()
                    
                    DeepSeek.wait_for_selector('textarea[id*="chat-input"], textarea[placeholder*="DeepSeek"]', timeout=60000)
                
            except Exception:
                try:
                    browser.close()
                except:
                    pass
                return
            
            context_target = browser.new_context()
            target = context_target.new_page()

            try:
                target.goto(starter_url, wait_until='domcontentloaded', timeout=60000)
            except Exception:
                pass

            found = False
            observation = "Агент запущен. Страница открыта: " + target.url
            
            while not found:
                request = f"""
ТЫ - БРАУЗЕРНЫЙ АГЕНТ.
ЗАДАЧА: {objective}
ТЕКУЩИЙ URL (в окне просмотра): {target.url}

ФОРМАТ ОТВЕТА (JSON):
Ты должен вернуть ТОЛЬКО JSON.

ВАРИАНТ 1: ДЕЙСТВОВАТЬ (ACTING)
{{
"status": "acting",
"thought": "Твое рассуждение...",
"actions": [
    {{ "tool": "go_to", "parameters": {{ "url": "..." }} }},
    {{ "tool": "search_elements", "parameters": {{ "keywords": ["..."], "tag": "..." }} }}
]
}}
(Ты можешь указать НЕСКОЛЬКО действий. Они будут выполнены последовательно.)

ВАРИАНТ 2: НАШЕЛ (FOUND)
{{
"status": "found",
"answer": "Здесь напиши итоговый ответ (цены, текст, данные)."
}}

ИНСТРУМЕНТЫ:
1. `search_elements`: Поиск текста. Параметры: `keywords` (list), `tag` (str), `attr` (opt).
2. `full_code`: Получить HTML (очищенный). Без параметров. Используй это, чтобы найти SELECTOR для клика или ввода.
3. `go_to`: Перейти по ссылке. Параметры: `url`.
4. `click_element`: Клик по элементу. Параметры: `selector`.
   ВАЖНО: Избегай селекторов с случайными ID (например, #uid_123, #react-id). Ищи стабильные атрибуты: `name="..."`, `aria-label="..."`, `placeholder="..."` или классы.
5. `fill_element`: Ввод текста. Параметры: `selector`, `text`.
   ВАЖНО: Используй переменные "$LOGIN", "$PASSWORD", "$GMAIL_LOGIN".
6. `check_email`: Проверить почту. Параметры: `keyword`. Возвращает текст письма.

РЕЗУЛЬТАТ ПРЕДЫДУЩИХ ДЕЙСТВИЙ:
{observation}
"""
                try:
                    textarea = DeepSeek.locator('textarea[id*="chat-input"], textarea[placeholder*="DeepSeek"]').first
                    textarea.fill(request)
                    textarea.press('Enter')
                    
                    time.sleep(2)
                    
                    prev_text = ""
                    stability_count = 0
                    
                    for _ in range(60): 
                        time.sleep(3)
                        
                        msgs = DeepSeek.locator('div.ds-markdown')
                        if msgs.count() > 0:
                            current_text = msgs.last.inner_text()
                            
                            if len(current_text) < 10:
                                continue

                            if current_text == prev_text:
                                stability_count += 1
                            else:
                                stability_count = 0
                                
                            prev_text = current_text
                            
                            is_json_complete = "}" in current_text[-10:] or "```" in current_text[-5:]
                            
                            if stability_count >= 2:
                                if is_json_complete:
                                    break
                                else:
                                    if stability_count >= 5:
                                        break
                        else:
                            pass
                    
                    response_text = prev_text
                    
                except Exception:
                    break

                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
                if not json_match:
                    observation = "ОШИБКА: Ты не вернул валидный JSON. Попробуй еще раз, строго по формату."
                    continue
                
                try:
                    data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    observation = "ОШИБКА: Невалидный JSON. Исправь синтаксис."
                    continue

                if data.get("status") == "found":
                    with open('final_result.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    found = True
                    break
                
                elif data.get("status") == "acting":
                    actions = data.get("actions", [])
                    new_observation_parts = []
                    
                    for action in actions:
                        t_name = action.get("tool")
                        params = action.get("parameters", {})
                        
                        try:
                            if t_name == "go_to":
                                url = params.get("url")
                                target.goto(url, wait_until='domcontentloaded', timeout=30000)
                                new_observation_parts.append(f"--- [ПЕРЕХОД ПО ССЫЛКЕ: {url}] ---")
                                new_observation_parts.append(f"Текущий URL: {target.url}")
                            
                            elif t_name == "full_code":
                                code = tool.html_cleaner(target.content())
                                code_str = str(code)[:15000] 
                                new_observation_parts.append(f"--- [HTML КОД ({len(code_str)} chars)] ---\\n{code_str}")
                                
                            elif t_name == "search_elements":
                                kw = params.get("keywords", [])
                                tag = params.get("tag", "div")
                                attr = params.get("attr")
                                found_els = tool.search_keywords(target.content(), kw, tag, attr)
                                txt_res = "\n".join([str(x) for x in found_els])
                                if len(txt_res) > 10000:
                                    txt_res = txt_res[:10000] + "\n...(обрезано)"
                                new_observation_parts.append(f"--- [РЕЗУЛЬТАТ ПОИСКА {kw}] ---\\nНайдено {len(found_els)} элементов:\n{txt_res}")
                                
                            elif t_name == "click_element":
                                selector = params.get("selector")
                                res = tool.click_element(target, selector)
                                new_observation_parts.append(res)

                            elif t_name == "fill_element":
                                selector = params.get("selector")
                                text_val = params.get("text")
                                res = tool.fill_element(target, selector, text_val, config)
                                new_observation_parts.append(res)

                            elif t_name == "check_email":
                                kw = params.get("keyword")
                                mail_res = mail_tool.get_latest_email(keyword=kw)
                                new_observation_parts.append(f"--- [ПОЧТА] ---\\n{mail_res}")
                                
                        except Exception as act_err:
                            new_observation_parts.append(f"[ОШИБКА {t_name}]: {act_err}")

                    observation = "\n\n".join(new_observation_parts)
                    if not observation:
                        observation = "Действия выполнены, но результат пустой."

if __name__ == "__main__":
    run_agent(
        objective="""
        1. Перейди на https://discord.com/register
        2. Заполни поля (ИЩИ ИХ ПО 'name' или 'aria-label', НЕ ПО id!):
           - Email: используй переменную $GMAIL_LOGIN
           - Display Name: 'Smart Agent'
           - Username: придумай уникальное имя (например 'Agent_Gemini_2026_Pro')
           - Password: используй переменную $DS_PASS
           - Date of Birth: выбери любую валидную дату (день, месяц, год).
        3. Нажми 'Continue' (Продолжить).
        4. ВАЖНО: Если появится CAPTCHA, подожди 40 секунд, пока пользователь её решит.
        5. Если появится сообщение 'Подтвердите email', вызови инструмент check_email с ключевым словом 'Discord'.
        6. Найди ссылку на подтверждение в письме и перейди по ней.
        """, 
        starter_url="https://discord.com/register"
    )