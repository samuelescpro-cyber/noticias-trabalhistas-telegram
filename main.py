import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
from urllib.parse import urljoin

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SITES = {
    "G1 MT": "https://g1.globo.com/mt/mato-grosso/"
}

def enviar(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "disable_web_page_preview": True
        }
    )

def coletar_noticias():
    noticias = []

    for fonte, url in SITES.items():
        html = requests.get(url, headers=HEADERS, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")

        # seletor REAL do G1
        for a in soup.select("a.feed-post-link"):
            link = a.get("href")
            titulo = a.get_text(strip=True)

            if link and titulo:
                noticias.append((fonte, titulo, link))

    return noticias[:5]

def main():
    noticias = coletar_noticias()

    # 🚨 SE NÃO TEM NOTÍCIA, NÃO ENVIA NADA
    if not noticias:
        return

    hoje = datetime.now().strftime("%d/%m/%Y")
    msg = f"⚖️ NOTÍCIAS TRABALHISTAS\n📅 {hoje}\n\n"

    for fonte, titulo, link in noticias:
        msg += f"📌 {titulo}\n🔗 {link}\n\n"

    enviar(msg)

if __name__ == "__main__":
    main()
