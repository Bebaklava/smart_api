import re
import time
import random
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup, Comment
from difflib import SequenceMatcher

class Tools:
    def __init__(self, threshold=0.7):
        self.threshold = threshold

    def html_cleaner(self, html_code):
        soup = BeautifulSoup(html_code, 'html.parser')
        for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
            comment.extract()
        junk_tags = ['script', 'style', 'video', 'audio', 'svg', 'iframe', 'noscript', 'link', 'meta', 'head', 'canvas', 'path']
        for junk_tag in soup.find_all(junk_tags):
            junk_tag.decompose()
        for hidden in soup.find_all(attrs={"style": re.compile(r'display:\s*none|visibility:\s*hidden')}):
            hidden.decompose()
        return soup

    def search_keywords(self, html_code, targets, tag='div', attr=None):
        soup = self.html_cleaner(html_code)
        matching_elements = []
        seen_texts = set()
        candidates = soup.find_all(tag)
        potential_matches = []
        for element in candidates:
            if attr:
                attr_value = element.get(attr, "")
                if isinstance(attr_value, list): attr_value = " ".join(attr_value)
                content_to_search = attr_value.lower()
            else:
                content_to_search = element.get_text(separator=' ', strip=True).lower()
            if not content_to_search: continue
            words_in_element = re.split(r'[ \-_,.;!?:()[\]\n\r\t]', content_to_search)
            words_in_element = [w for w in words_in_element if w]
            if self._has_matching(words_in_element, targets):
                potential_matches.append(element)
        for i, elem_a in enumerate(potential_matches):
            is_parent = False
            a_text = elem_a.get_text(strip=True)
            for j, elem_b in enumerate(potential_matches):
                if i != j and elem_b in elem_a.descendants:
                    is_parent = True
                    break
            if not is_parent and a_text not in seen_texts:
                matching_elements.append(elem_a)
                seen_texts.add(a_text)
        return matching_elements

    def _has_matching(self, source, targets):
        for target in targets:
            target_lower = target.lower()
            for word in source:
                if target_lower in word: return True
                if SequenceMatcher(None, target_lower, word).ratio() >= self.threshold: return True
        return False

    def click_element(self, page, selector):
        try:
            page.wait_for_selector(selector, state="visible", timeout=10000)
            # Двигаем мышку к элементу перед кликом (имитация человека)
            el = page.locator(selector).first
            el.hover()
            time.sleep(random.uniform(0.2, 0.5))
            el.click(timeout=5000)
            return f"--- [КЛИК ПО: {selector}] ---"
        except Exception as e:
            return f"ОШИБКА КЛИКА ({selector}): {e}"

    def fill_element(self, page, selector, text, config=None):
        if text == "$LOGIN" and config: text = config.DS_LOGIN
        elif text == "$PASSWORD" and config: text = config.DS_PASS
        elif text == "$GMAIL_LOGIN" and config: text = config.GMAIL_LOGIN
        try:
            page.wait_for_selector(selector, state="visible", timeout=10000)
            el = page.locator(selector).first
            el.click() # Сначала кликаем в поле
            el.fill("") # Очищаем
            # Вводим посимвольно для обхода защит
            for char in text:
                page.keyboard.type(char)
                time.sleep(random.uniform(0.05, 0.15))
            return f"--- [ВВОД В {selector}] ---"
        except Exception as e:
            return f"ОШИБКА ВВОДА ({selector}): {e}"

    def scroll_page(self, page, direction="down"):
        try:
            if direction == "down":
                page.evaluate("window.scrollBy(0, 500)")
            else:
                page.evaluate("window.scrollBy(0, -500)")
            time.sleep(1)
            return f"--- [СКРОЛЛ: {direction}] ---"
        except Exception as e:
            return f"ОШИБКА СКРОЛЛА: {e}"

    def wait(self, seconds):
        time.sleep(seconds)
        return f"--- [ОЖИДАНИЕ {seconds} сек.] ---"