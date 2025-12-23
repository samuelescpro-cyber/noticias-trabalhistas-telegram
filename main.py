import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
import os

# ======================
# CONFIGURAÇÕES
# ======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RSS_FEEDS = [
    "https://www.conjur.com.br/rss/area/trabalhista",
    "https://www.migalhas.com.br/rss/trabalhista"
]

# ======================
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

# ======================
def resumir_texto(html):
    soup = BeautifulSoup(html, "html.parser")
    texto = soup.get_text(separator=" ", strip=True)
    return texto[:400] + "..." if len(texto) > 400 else texto

# ======================
def main():
    hoje = datetime.now().strftime("%d/%m/%Y")
    mensagem = f"⚖️ <b>NOTÍCIAS TRABALHISTAS</b>\n📅 {hoje}\n\n"

    total_noticias = 0

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        if not feed.entries:
            continue

        for entry in feed.entries[:3]:
            titulo = entry.title
            link = entry.link

            try:
                html = requests.get(link, timeout=10).text
                resumo = resumir_texto(html)
            except:
                resumo = "Resumo indisponível."

            mensagem += (
                f"📌 <b>{titulo}</b>\n"
                f"📝 {resumo}\n"
                f"🔗 {link}\n\n"
                "———————————————\n\n"
            )
            total_noticias += 1

    if total_noticias == 0:
        mensagem += "⚠️ Nenhuma notícia encontrada hoje."

    enviar_telegram(mensagem)

# ======================
if __name__ == "__main__":
    main()
