import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from openai import OpenAI

# ======================
# SECRETS
# ======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not OPENAI_API_KEY:
    raise Exception("Secrets obrigatórios não configurados")

# ======================
# CONFIG
# ======================
HIST_FILE = ".github/enviadas.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (NoticiasTrabalhistasBot/1.0)"
}

SOURCES = {
    "TRT-23": "https://portal.trt23.jus.br/portal/noticias",
    "G1 MT": "https://g1.globo.com/mt/mato-grosso/",
    "Olhar Direto": "https://www.olhardireto.com.br/",
    "Reporter MT": "https://www.reportermt.com/",
    "Gazeta Digital": "https://www.gazetadigital.com.br/",
    "Folha Max": "https://www.folhamax.com/",
    "Estadão MT": "https://www.estadaomatogrosso.com.br"
}

KEYWORDS = [
    # política
    "governo", "prefeito", "deputado", "assembleia", "senado",
    "política", "eleição", "campanha",

    # crimes / polícia
    "crime", "polícia", "prisão", "preso", "assassinato",
    "homicídio", "furto", "roubo", "tráfico", "operação",

    # geral (pra garantir)
    "mt", "mato grosso"
]

client = OpenAI(api_key=OPENAI_API_KEY)

# ======================
def carregar_historico():
    if os.path.exists(HIST_FILE):
        with open(HIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_historico(data):
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def enviar_telegram(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
    )

# ======================
def texto_relevante(texto):
    texto = texto.lower()
    return any(k in texto for k in KEYWORDS)


def resumo_juridico(texto):
    prompt = f"""
Você é um jornalista.
Resuma o texto abaixo em até 3 linhas, de forma clara e objetiva.

Texto:
{texto}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()


# ======================
from urllib.parse import urljoin

def extrair_links(url):
    html = requests.get(url, headers=HEADERS, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        # ignora âncoras e javascript
        if href.startswith("#") or href.startswith("javascript"):
            continue

        # converte link relativo em absoluto
        full_url = urljoin(url, href)

        # filtro simples pra evitar lixo
        if full_url.startswith("http"):
            links.add(full_url)

    return list(links)[:30]

# ======================
def main():
    historico = carregar_historico()
    novos = []

    hoje = datetime.now().strftime("%d/%m/%Y")
    mensagem = f"⚖️ <b>JUSTIÇA DO TRABALHO – MT</b>\n📅 {hoje}\n\n"

    for fonte, url in SOURCES.items():
        try:
            links = extrair_links(url)
        except:
            continue

        for link in links:
            if link in historico:
                continue

            try:
                page = requests.get(link, headers=HEADERS, timeout=20).text
                texto = BeautifulSoup(page, "html.parser").get_text(" ", strip=True)
            except:
                continue

            if not texto_relevante(texto):
                continue

            texto = texto[:4000]  # controle de custo

            resumo = resumo_juridico(texto)

            if resumo == "DESCARTAR":
                continue

            mensagem += (
                f"📌 <b>{fonte}</b>\n"
                f"📝 {resumo}\n"
                f"🔗 {link}\n\n"
                "———————————————\n\n"
            )

            novos.append(link)

    if novos:
        enviar_telegram(mensagem)
        historico.extend(novos)
        salvar_historico(historico)

if __name__ == "__main__":
    main()
