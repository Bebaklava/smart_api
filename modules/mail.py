import imaplib
import email
from email.header import decode_header
import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    import config
except ImportError:
    pass

class MailClient:
    def __init__(self):
        self.imap_server = "imap.gmail.com"
        self.email_user = getattr(config, 'GMAIL_LOGIN', None)
        self.email_pass = getattr(config, 'GMAIL_APP_PASS', None)

    def get_latest_email(self, keyword=None, limit=3):
        if not self.email_user or "YOUR_GMAIL" in self.email_user:
            return "ОШИБКА: Не настроен GMAIL_LOGIN в config.py"

        try:
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_user, self.email_pass)
            mail.select("inbox")

            status, messages = mail.search(None, "ALL")
            if status != "OK":
                return "Нет писем в ящике."

            mail_ids = messages[0].split()
            latest_ids = mail_ids[-limit:]
            
            results = []

            for i in reversed(latest_ids):
                res, msg_data = mail.fetch(i, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        
                        from_ = msg.get("From")

                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                if "attachment" not in content_disposition:
                                    if content_type == "text/plain":
                                        body = part.get_payload(decode=True).decode()
                                        break 
                        else:
                            body = msg.get_payload(decode=True).decode()

                        full_text = f"Subject: {subject}\nFrom: {from_}\nBody: {body}"
                        
                        if keyword:
                            if keyword.lower() in subject.lower() or keyword.lower() in body.lower():
                                return f"--- НАЙДЕНО ПИСЬМО ---\n{full_text[:2000]}"
                        else:
                            results.append(f"--- ПИСЬМО ---\n{full_text[:500]}...")

            mail.close()
            mail.logout()

            if keyword:
                return f"Письмо с ключевым словом '{keyword}' не найдено среди последних {limit}."
            
            return "\n\n".join(results) if results else "Письма не найдены."

        except Exception as e:
            return f"ОШИБКА проверки почты: {e}"