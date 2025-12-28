import time
import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

class Tools:
    def __init__(self, threshold = 0.7):
        self.threshold = threshold

    # Поиск по словам
    def search_keywords(self, html_code, list):
        soup = BeautifulSoup(html_code, 'html.parser')
        matching_divs = []

        for div in soup.find_all('div'):
            div_text = re.split(r'[ \-_,.;!]', div.get_text(separator=' ').lower())
            if self._has_matching(div_text, list):
                matching_divs.append(div)
        return matching_divs

    def _has_matching(self, source, targets):
        for target in targets:
            for word in source:
                if SequenceMatcher(None, target.lower(), word.lower()).ratio() >= self.threshold:
                    return True
        return False
    # Поиска по словам

