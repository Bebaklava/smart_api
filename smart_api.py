import time
import json
import re
import sys
import io
import random
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
    with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox", 
                    "--disable-setuid-sandbox", 
                    "--disable-blink-features=AutomationControlled",
                    "--use-fake-ui-for-media-stream"
                ]
            )
            
            tool = tools.Tools()
            mail_tool = mail.MailClient()

            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            
            context_ds = browser.new_context(user_agent=user_agent, locale="ru-RU")
            DeepSeek = context_ds.new_page()
            
            try:
                DeepSeek.goto('https://chat.deepseek.com/sign-in', wait_until='networkidle', timeout=60000)
                if "YOUR_PHONE" in config.DS_LOGIN or "YOUR_PASS" in config.DS_PASS:
                    DeepSeek.wait_for_selector('textarea[id*="chat-input"]', timeout=120000)
                else:
                    if DeepSeek.locator('input[placeholder*="Номер телефона"], input[placeholder*="Email"]').count() > 0:
                        DeepSeek.fill('input[placeholder*="Номер телефона"], input[placeholder*="Email"]', config.DS_LOGIN)
                        time.sleep(1)
                        DeepSeek.fill('input[type="password"]', config.DS_PASS)
                        time.sleep(1)
                        DeepSeek.get_by_role("button", name=re.compile(r"Войти|Log In", re.I)).click()
                    DeepSeek.wait_for_selector('textarea[id*="chat-input"]', timeout=60000)
                
                # Сброс чата
                try:
                    DeepSeek.get_by_role("button", name="New Chat").click(timeout=5000)
                    time.sleep(2)
                except: pass
                
            except Exception as e:
                sys.stderr.write(f"[!] DeepSeek Init Error: {e}\n")
                return
            
            context_target = browser.new_context(user_agent=user_agent, locale="en-US", viewport={"width": 1280, "height": 720})
            context_target.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            target = context_target.new_page()

            try:
                target.goto(starter_url, wait_until='networkidle', timeout=60000)
                time.sleep(3)
            except Exception as e:
                sys.stderr.write(f"[!] Target Load Error: {e}\n")

            found = False
            observation = "Агент запущен. Страница загружена. Сначала используй full_code."
            iteration = 0
            
            while not found:
                iteration += 1
                print(f"\n--- Итерация {iteration} ---")
                
                request = f"""
Ты — локальный скрипт автоматизации. Твоя цель: {objective}
Текущий URL: {target.url}

Инструкция:
1. Всегда начинай с `full_code`.
2. Используй `fill_element`, `click_element`, `scroll_page`, `wait`.
3. В `fill_element` используй $LOGIN, $PASSWORD, $GMAIL_LOGIN.

ФОРМАТ ОТВЕТА (JSON):
{{
"status": "acting",
"thought": "Твое краткое рассуждение (на русском)...",
"actions": [
    {{ "tool": "full_code", "parameters": {{}} }}
]
}}

ИНСТРУМЕНТЫ:
- `full_code`: {{}} - получить очищенный HTML.
- `click_element`: {{"selector": "..."}} - клик.
- `fill_element`: {{"selector": "...", "text": "..."}} - ввод текста.
- `scroll_page`: {{"direction": "down/up"}} - прокрутка.
- `wait`: {{"seconds": 5}} - ожидание.
- `check_email`: {{"keyword": "..."}} - проверка почты.
- `go_to`: {{"url": "..."}} - переход.

Предыдущие действия:
{observation}
"""
                try:
                    textarea = DeepSeek.locator('textarea[id*="chat-input"]').first
                    textarea.fill(request)
                    textarea.press('Enter')
                    
                    prev_text = ""
                    stability_count = 0
                    for _ in range(60): 
                        time.sleep(3)
                        msgs = DeepSeek.locator('div.ds-markdown')
                        if msgs.count() > 0:
                            current_text = msgs.last.inner_text()
                            if len(current_text) < 10: continue
                            if current_text == prev_text: stability_count += 1
                            else: stability_count = 0
                            prev_text = current_text
                            if stability_count >= 2 and ("}" in current_text[-10:] or "```" in current_text[-5:]): break
                    response_text = prev_text
                except Exception as e:
                    sys.stderr.write(f"[!] DeepSeek Loop Error: {e}\n")
                    break

                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
                if not json_match:
                    observation = "ОШИБКА: Ты не вернул JSON. Попробуй еще раз."
                    continue
                
                try:
                    data = json.loads(json_match.group(1))
                except:
                    observation = "ОШИБКА: Битый JSON."
                    continue

                print(f"Мысль: {data.get('thought')}")
                print(f"Статус: {data.get('status')}")

                if data.get("status") == "found":
                    print(f"УСПЕХ: {data.get('answer')}")
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
                            if t_name == "full_code":
                                code_str = str(tool.html_cleaner(target.content()))[:15000] 
                                new_observation_parts.append(f"--- [HTML КОД ({len(code_str)} chars)] ---\n{code_str}")
                            elif t_name == "click_element":
                                new_observation_parts.append(tool.click_element(target, params.get("selector")))
                            elif t_name == "fill_element":
                                new_observation_parts.append(tool.fill_element(target, params.get("selector"), params.get("text"), config))
                            elif t_name == "scroll_page":
                                new_observation_parts.append(tool.scroll_page(target, params.get("direction", "down")))
                            elif t_name == "wait":
                                new_observation_parts.append(tool.wait(params.get("seconds", 3)))
                            elif t_name == "check_email":
                                new_observation_parts.append(f"--- [ПОЧТА] ---\n{mail_tool.get_latest_email(keyword=params.get('keyword'))}")
                            elif t_name == "go_to":
                                target.goto(params.get("url"), wait_until='networkidle', timeout=30000)
                                new_observation_parts.append(f"--- [ПЕРЕХОД: {target.url}] ---")
                        except Exception as act_err:
                            new_observation_parts.append(f"[ОШИБКА {t_name}]: {act_err}")
                    observation = "\n\n".join(new_observation_parts)

if __name__ == "__main__":
    run_agent("Зарегестрируйся на Hugging Face (https://huggingface.co/join) используя $GMAIL_LOGIN и $DS_PASS. Если нужно подтверждение почты - используй check_email.", "https://huggingface.co/join")
