import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from openai import OpenAI

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

HIST_FILE = "enviadas.json"

SOURCES = {
    "TRT23": "https://portal.trt23.jus.br/portal/noticias",
    "G1_MT": "https://g1.globo.com/mt/mato-grosso/",
    "OlharDireto": "https://www.olhardireto.com.br/",
    "ReporterMT": "https://www.reportermt.com/",
    "GazetaDigital": "https://www.gazetadigital.com.br/",
    "FolhaMax": "https://www.folhamax.com/",
    "EstadaoMT": "https://www.estadaomatogrosso.com.br"
}

KEYWORDS = [
    "trabalhista", "trabalho", "empregado", "empregador",
    "justiça do trabalho", "TRT", "TRT-23", "ação trabalhista",
    "processo trabalhista", "verbas rescisórias", "CLT",
    "horas extras", "FGTS", "rescisão", "assédio",
    "vínculo empregatício"
]

client = OpenAI(api_key=OPENAI_API_KEY)

# ------------------------
def carregar_historico():
    if os.path.exists(HIST_FILE):
        return json.load(open(HIST_FILE, "r", encoding="utf-8"))
    return []

def salvar_historico(data):
    json.dump(data, open(HIST_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

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

# ------------------------
def texto_relevante(texto):
    texto_lower = texto.lower()
    return any(k in texto_lower for k in KEYWORDS)

def resumo_juridico(texto):
    prompt = f"""
Você é um jornalista jurídico especializado em Direito do Trabalho.
Analise o texto abaixo.

1) Confirme se trata de processo, decisão ou ação trabalhista ocorrida no Estado de Mato Grosso.
2) Se NÃO for, responda apenas: DESCARTAR
3) Se for, gere um resumo jurídico jornalístico, técnico e objetivo (máx. 5 linhas).

Texto:
{texto}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return resp.choices[0].message.content.strip()

# ------------------------
def extrair_links(url):
    html = requests.get(url, timeout=15).text
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http"):
            links.append(href)
    return list(set(links))[:20]

# ------------------------
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
                page = requests.get(link, timeout=15).text
                texto = BeautifulSoup(page, "html.parser").get_text(" ", strip=True)
            except:
                continue

            if not texto_relevante(texto):
                continue

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
