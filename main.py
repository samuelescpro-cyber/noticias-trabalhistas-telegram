import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

URL = "https://g1.globo.com/mt/mato-grosso/"

def enviar(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "disable_web_page_preview": True
        }
    )

html = requests.get(URL, headers=HEADERS).text
soup = BeautifulSoup(html, "html.parser")

links = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    if "/mt/" in href:
        if href.startswith("http"):
            links.append(href)

links = list(dict.fromkeys(links))[:5]

hoje = datetime.now().strftime("%d/%m/%Y")
msg = f"🧪 TESTE G1 MT – {hoje}\n\n"

for l in links:
    msg += f"{l}\n\n"

enviar(msg)
