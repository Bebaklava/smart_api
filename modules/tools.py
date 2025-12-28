import re
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

        junk_tags = [
            'script', 'style', 'video', 'audio', 'svg', 'iframe', 
            'noscript', 'link', 'meta', 'head', 'canvas', 'path'
        ]

        for junk_tag in soup.find_all(junk_tags):
            junk_tag.decompose()

        for hidden in soup.find_all(attrs={"style": re.compile(r'display:\s*none|visibility:\s*hidden')}):
            hidden.decompose()

        return soup

    def search_keywords(self, html_code, targets, tag='div'):
        soup = self.html_cleaner(html_code)
        
        matching_elements = []
        seen_texts = set()
        self.tag = tag
        candidates = soup.find_all(self.tag)

        potential_matches = []
        for element in candidates:
            text_content = element.get_text(separator=' ', strip=True)
            if not text_content:
                continue
                
            words_in_element = re.split(r'[ \-_,.;!?:()\[\]\n\r\t]', text_content.lower())
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
                if target_lower in word:
                    return True
                if SequenceMatcher(None, target_lower, word).ratio() >= self.threshold:
                    return True
        return False