import os
import json
import time
import re
import html
import requests
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from bs4 import BeautifulSoup

# ======================
# CONFIG / ENV
# ======================
DEBUG = os.getenv("DEBUG", "0") == "1"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

HIST_FILE = "enviadas.json"

TIMEOUT = (7, 20)  # (conexão, leitura)
SLEEP = float(os.getenv("SLEEP", "0.25"))

MAX_LINKS_POR_FONTE = int(os.getenv("MAX_LINKS_POR_FONTE", "40"))
MAX_PAGINAS_ANALISADAS = int(os.getenv("MAX_PAGINAS_ANALISADAS", "120"))

MAX_RELEVANTES = int(os.getenv("MAX_RELEVANTES", "7"))
MAX_OUTRAS = int(os.getenv("MAX_OUTRAS", "12"))

# Se TRUE: mais rígido (exige score >= 2, exceto TRT23)
STRICT_JT = os.getenv("STRICT_JT", "1") == "1"

# Mostrar ou não a seção "OUTRAS (AINDA JT)"
SHOW_OUTRAS = os.getenv("SHOW_OUTRAS", "1") == "1"

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise SystemExit("ERRO: Defina TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no ambiente.")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TelegramNewsBot/1.0",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# ======================
# FONTES
# ======================
SOURCES = [
    # TRT23 (prioridade)
    "https://portal.trt23.jus.br/portal/noticias",
    "https://portal.trt23.jus.br/portal/noticias?page=1",

    # Novas fontes pedidas
    "https://lucasdorioverde.portaldacidade.com/",
    "https://www.conjur.com.br/",
    "https://cpanoticias.com/",
    "https://www.cnj.jus.br/poder-judiciario/tribunais/tribunal-regional-do-trabalho-da-23a-regiao-trt23/",

    # Portais MT / Jurídico (só entra se for JT)
    "https://g1.globo.com/mt/mato-grosso/",
    "https://www.olhardireto.com.br/",
    "https://www.olhardireto.com.br/juridico/",
    "https://www.reportermt.com/",
    "https://www.reportermt.com/ultimas-noticias",
    "https://www.gazetadigital.com.br/",
    "https://www.gazetadigital.com.br/editorias/judiciario/",
    "https://www.folhamax.com/",
    "https://www.folhamax.com/cidades/",
    "https://www.folhamax.com/politica/",
    "https://www.tjmt.jus.br/noticias",
    "https://www.estadaomatogrosso.com.br",
]

# ======================
# FILTRO: SOMENTE JUSTIÇA DO TRABALHO
# ======================
JT_STRONG = [
    "justiça do trabalho", "justica do trabalho",
    "trt", "trt-23", "trt23", "trtmt",
    "vara do trabalho", "varas do trabalho",
    "tst",
    "mpt", "ministério público do trabalho", "ministerio publico do trabalho",
    "clt",
    "reclamação trabalhista", "reclamacao trabalhista",
    "ação trabalhista", "acao trabalhista",
    "processo trabalhista",
    "empregado", "empregador",
    "verbas rescisórias", "verbas rescisorias",
    "fgts", "horas extras",
    "rescisão", "rescisao",
    "acordo trabalhista",
    "convenção coletiva", "convencao coletiva",
    "dissídio", "dissidio",
    "assédio", "assedio",
    "insalubridade", "periculosidade",
    "vínculo empregatício", "vinculo empregaticio",
]

JT_WEAK = [
    "trabalh",  # trabalhista/trabalhador etc.
    "sindicato", "greve",
]

def jt_score(title: str, text: str, url: str) -> int:
    t = (title + " " + text).lower()
    score = 0

    for k in JT_STRONG:
        if k in t:
            score += 2

    for k in JT_WEAK:
        if k in t:
            score += 1

    netloc = urlparse(url).netloc.lower()
    if "trt23.jus.br" in netloc:
        score += 4
    elif "trt" in netloc:
        score += 2

    return score

def is_justica_do_trabalho(title: str, text: str, url: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    if "trt23.jus.br" in netloc:
        return True

    score = jt_score(title, text, url)
    return score >= (2 if STRICT_JT else 1)

def is_relevante_trt23(title: str, text: str, url: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    if "trt23.jus.br" in netloc:
        return True

    if not is_justica_do_trabalho(title, text, url):
        return False

    t = (title + " " + text).lower()
    sinais_mt_trt23 = [
        "trt-23", "trt23", "trtmt",
        "mato grosso", " mt ", "cuiab", "várzea", "varzea",
        "rondonópolis", "rondonopolis",
        "sinop", "sorriso", "primavera do leste",
    ]
    return any(s in t for s in sinais_mt_trt23)

# ======================
# UTILIDADES
# ======================
def load_hist():
    if os.path.exists(HIST_FILE):
        try:
            with open(HIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data if isinstance(data, list) else [])
        except Exception:
            return set()
    return set()

def save_hist(hist: set):
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(hist)), f, ensure_ascii=False, indent=2)

def telegram_send(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=TIMEOUT,
    )
    if DEBUG:
        print("TELEGRAM:", r.status_code, r.text[:180])
    r.raise_for_status()

def chunk_telegram(msg: str, limit=3800):
    parts, buf = [], ""
    for line in msg.splitlines(True):
        if len(buf) + len(line) > limit:
            parts.append(buf)
            buf = ""
        buf += line
    if buf.strip():
        parts.append(buf)
    return parts

def good_url(u: str) -> bool:
    bad_ext = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".pdf", ".mp4", ".mp3", ".zip")
    return not u.lower().endswith(bad_ext)

def same_domain(base, u) -> bool:
    b = urlparse(base).netloc.lower()
    n = urlparse(u).netloc.lower()
    if not b or not n:
        return False

    if b in n:
        return True
    if "globo.com" in b and "globo.com" in n:
        return True
    return False

def clean_olhar_url(u: str) -> str:
    # remove caractere estranho "¬" e tenta normalizar query
    if not any(d in u for d in ("olhardireto.com.br", "olharjuridico.com.br", "olharconceito.com.br")):
        return u

    u = u.replace("¬", "")
    parsed = urlparse(u)
    qs = parse_qs(parsed.query, keep_blank_values=True)

    # alguns links quebram "noticia" virando "icia"
    if "icia" in qs and "noticia" not in qs:
        qs["noticia"] = qs.pop("icia")

    new_query = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

def normalize_url(u: str) -> str:
    """Remove fragment + alguns trackers comuns pra dedupe melhor."""
    parsed = urlparse(u)
    qs = parse_qs(parsed.query, keep_blank_values=True)

    drop_keys = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}
    for k in list(qs.keys()):
        if k in drop_keys:
            qs.pop(k, None)

    new_query = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ""))

def fetch(url: str) -> str:
    # retry simples
    last_err = None
    for attempt in range(2):
        try:
            time.sleep(SLEEP)
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            time.sleep(0.6 * (attempt + 1))
    raise last_err

def looks_like_article(source_url: str, u: str) -> bool:
    """Heurística por site pra evitar páginas inúteis (menu/seções)."""
    netloc = urlparse(u).netloc.lower()
    path = urlparse(u).path.lower()

    # TRT23: só pega notícias mesmo
    if "portal.trt23.jus.br" in netloc:
        return ("/portal/noticias/" in path) and ("menulistchildren" not in path) and ("page=" not in u)

    # G1 MT: notícia .ghtml
    if "g1.globo.com" in netloc:
        return ("/noticia/" in path) and u.endswith(".ghtml")

    # Olhar: exibir.asp com id (normalmente notícia)
    if "olhardireto.com.br" in netloc or "olharjuridico.com.br" in netloc or "olharconceito.com.br" in netloc:
        return ("exibir.asp" in path) and ("id=" in u)

    # FolhaMax: geralmente tem número no final
    if "folhamax.com" in netloc:
        return bool(re.search(r"/\d{3,}$", path))

    # Repórter MT: costuma ter /<categoria>/<slug>/<id>
    if "reportermt.com" in netloc:
        return bool(re.search(r"/\d{3,}$", path))

    # Gazeta: costuma ter /.../123456
    if "gazetadigital.com.br" in netloc:
        return bool(re.search(r"/\d{3,}$", path))

    # Estadao MT: /.../123456
    if "estadaomatogrosso.com.br" in netloc:
        return bool(re.search(r"/\d{3,}$", path))

    # ConJur: costuma ser /YYYY/mm/dd/
    if "conjur.com.br" in netloc:
        return bool(re.search(r"/\d{4}/\d{2}/\d{2}/", path))

    # Portal da Cidade: costuma ter /noticias/ ou /economia/ etc, mas artigo tem slug maior
    if "portaldacidade.com" in netloc:
        return len(path.strip("/").split("/")) >= 2

    # CNJ: páginas institucionais (quase não terá notícia), deixa passar e o filtro JT decide
    return True

def extract_links(source_url: str):
    html_ = fetch(source_url)
    soup = BeautifulSoup(html_, "html.parser")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue

        u = urljoin(source_url, href).split("#")[0]
        u = clean_olhar_url(u)
        u = normalize_url(u)

        if not good_url(u):
            continue
        if not same_domain(source_url, u):
            continue
        if not looks_like_article(source_url, u):
            continue

        links.append(u)

    # dedupe preservando ordem
    seen, out = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)

    return out[:MAX_LINKS_POR_FONTE]

def get_title_text_time_source(url: str):
    html_ = fetch(url)
    soup = BeautifulSoup(html_, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # title
    title = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True)
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    # text
    article = soup.find("article")
    text = article.get_text(" ", strip=True) if article else soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()

    # hora (quando existir)
    m = re.search(r"\b([01]\d|2[0-3])[:h]([0-5]\d)\b", text)
    hhmm = f"{m.group(1)}:{m.group(2)}" if m else None

    # fonte display
    netloc = urlparse(url).netloc.lower()
    fonte = netloc
    if "g1.globo.com" in netloc:
        fonte = "G1 Mato Grosso" if "/mt/" in url else "G1"
    elif "portal.trt23.jus.br" in netloc:
        fonte = "TRT23"
    elif "reportermt.com" in netloc:
        fonte = "Repórter MT"
    elif "gazetadigital.com.br" in netloc:
        fonte = "Gazeta Digital"
    elif "folhamax.com" in netloc:
        fonte = "FolhaMax"
    elif "tjmt.jus.br" in netloc:
        fonte = "TJMT"
    elif "estadaomatogrosso.com.br" in netloc:
        fonte = "Estadão Mato Grosso"
    elif "olhardireto.com.br" in netloc:
        fonte = "Olhar Direto"
    elif "olharjuridico.com.br" in netloc:
        fonte = "Olhar Jurídico"
    elif "olharconceito.com.br" in netloc:
        fonte = "Olhar Conceito"
    elif "conjur.com.br" in netloc:
        fonte = "ConJur"
    elif "cpanoticias.com" in netloc:
        fonte = "CPA Notícias"
    elif "portaldacidade.com" in netloc:
        fonte = "Portal da Cidade"
    elif "cnj.jus.br" in netloc:
        fonte = "CNJ"

    return (title[:220].strip(), text, hhmm, fonte)

def fmt_item(title: str, hhmm: str | None, fonte: str, url: str, numbered=False, n=1) -> str:
    safe_title = html.escape(title.strip())
    safe_url = html.escape(url)

    if hhmm:
        head = f"{hhmm} - {safe_title} ({html.escape(fonte)})"
    else:
        head = f"{safe_title} ({html.escape(fonte)})"

    if numbered:
        return f"{n}) {head}\n    {safe_url}\n"
    else:
        return f"- {head}\n  {safe_url}\n"

# ======================
# MAIN
# ======================
def main():
    hist = load_hist()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    relevantes = []
    outras = []
    analyzed = 0

    for src in SOURCES:
        if DEBUG:
            print("\n=== FONTE:", src)

        try:
            links = extract_links(src)
            if DEBUG:
                print("Links coletados:", len(links))
        except Exception as e:
            if DEBUG:
                print("Falha ao coletar:", src, e)
            continue

        for link in links:
            if analyzed >= MAX_PAGINAS_ANALISADAS:
                break

            link = normalize_url(link)
            if link in hist:
                continue

            analyzed += 1
            if DEBUG:
                print("GET:", link)

            try:
                title, text, hhmm, fonte = get_title_text_time_source(link)
            except Exception as e:
                if DEBUG:
                    print("Falha ao abrir:", link, e)
                continue

            if not title or len(text) < 200:
                continue

            # >>> SOMENTE JUSTIÇA DO TRABALHO <<<
            if not is_justica_do_trabalho(title, text, link):
                continue

            if is_relevante_trt23(title, text, link):
                relevantes.append((title, hhmm, fonte, link))
            else:
                outras.append((title, hhmm, fonte, link))

            hist.add(link)

            if len(relevantes) >= MAX_RELEVANTES and (not SHOW_OUTRAS or len(outras) >= MAX_OUTRAS):
                break

    save_hist(hist)

    # ======================
    # MENSAGEM NO FORMATO PEDIDO
    # ======================
    msg = []
    msg.append(f"📅 {agora}")
    msg.append("⚖️ <b>NOTICIAS RELEVANTES PARA O TRT23</b>")
    msg.append("")

    msg.append("<b>RELEVANTES TRT23:</b>")
    if relevantes:
        for i, (title, hhmm, fonte, link) in enumerate(relevantes[:MAX_RELEVANTES], start=1):
            msg.append(fmt_item(title, hhmm, fonte, link, numbered=True, n=i).rstrip())
    else:
        msg.append("(nenhuma notícia de Justiça do Trabalho relevante para o TRT23 encontrada)")

    if SHOW_OUTRAS:
        msg.append("")
        msg.append("<b>OUTRAS (AINDA JT):</b>")
        if outras:
            for (title, hhmm, fonte, link) in outras[:MAX_OUTRAS]:
                msg.append(fmt_item(title, hhmm, fonte, link, numbered=False).rstrip())
        else:
            msg.append("(nenhuma)")

    full = "\n".join(msg).strip()

    parts = chunk_telegram(full)
    if DEBUG:
        print("Enviando Telegram (partes):", len(parts))

    for p in parts:
        telegram_send(p)

if __name__ == "__main__":
    main()


