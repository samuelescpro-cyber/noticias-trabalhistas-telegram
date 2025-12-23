import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime

# ======================
# CONFIGURAÇÕES
# ======================
TELEGRAM_TOKEN = "8317964744:AAHkHaY3b-qgU3MX0ELpf5nxnHEqDP0P9hY"
TELEGRAM_CHAT_ID = "5361085564"

# Fontes RSS (pode adicionar mais)
RSS_FEEDS = [
    "https://www.conjur.com.br/rss/area/trabalhista",
    "https://www.migalhas.com.br/rss/trabalhista"
    "https://www.olhardireto.com.br/"
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
    return texto[:500] + "..." if len(texto) > 500 else texto

# ======================
def main():
    hoje = datetime.now().strftime("%d/%m/%Y")
    cabecalho = f"⚖️ <b>NOTÍCIAS TRABALHISTAS</b>\n📅 {hoje}\n\n"
    mensagem_final = cabecalho

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:3]:
            titulo = entry.title
            link = entry.link

            try:
                html = requests.get(link, timeout=10).text
                resumo = resumir_texto(html)
            except:
                resumo = "Não foi possível extrair o resumo."

            mensagem_final += (
                f"📌 <b>{titulo}</b>\n\n"
                f"📝 {resumo}\n\n"
                f"🔗 {link}\n\n"
                "———————————————\n\n"
            )

    enviar_telegram(mensagem_final)

# ======================
if __name__ == "__main__":
    main()
