import os
import json
import time
import re
import html as htmlmod
import unicodedata
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

TIMEOUT = (7, 20)
SLEEP = float(os.getenv("SLEEP", "0.25"))

MAX_LINKS_POR_FONTE = int(os.getenv("MAX_LINKS_POR_FONTE", "80"))
MAX_PAGINAS_ANALISADAS = int(os.getenv("MAX_PAGINAS_ANALISADAS", "400"))
MAX_RELEVANTES_MT = int(os.getenv("MAX_RELEVANTES_MT", "15"))
MAX_RELEVANTES_BR = int(os.getenv("MAX_RELEVANTES_BR", "15"))

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise SystemExit("ERRO: Defina TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no ambiente.")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TelegramNewsBot/2.0",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# ======================
# FONTES
# ======================

SOURCES_MT = [
    "https://g1.globo.com/mt/mato-grosso/",
    "https://www.olhardireto.com.br/",
    "https://www.reportermt.com/",
    "https://www.gazetadigital.com.br/",
    "https://www.folhamax.com/",
    "https://cpanoticias.com/",
    "https://portal.trt23.jus.br/portal/noticias",
]

SOURCES_BR = [
    "https://g1.globo.com/",
    "https://www.conjur.com.br/",
    "https://www.poder360.com.br/",
    "https://agenciabrasil.ebc.com.br/",
    "https://valor.globo.com/",
    "https://www.cnnbrasil.com.br/",
    "https://www.estadao.com.br/",
]

# ======================
# BLOQUEIOS
# ======================
BLOCKED_DOMAINS = {
    "globoplay.globo.com",
    "ge.globo.com",
    "gshow.globo.com",
}

BLOCKED_PATH_SNIPPETS = [
    "/live/", "/ao-vivo/", "/aovivo/",
    "/videos/", "/video/", "/player/",
    "/podcasts/", "/podcast/",
    "/programas/", "/apps/", "/app/",
    "/tv/", "/radio/",
    "/especiais/", "/especial/",
    "/galeria/", "/fotos/", "/foto/",
    "/tag/", "/tags/", "/topicos/", "/assunto/",
    "/newsletter/", "/newsletters/",
    "/login", "/cadastro", "/assinatura", "/subscribe",
    "/privacidade", "/privacy", "/politica-de-privacidade",
    "/termos", "/terms",
    "/contato", "/fale-conosco", "/expediente", "/sobre",
    "/institucional", "/quem-somos",
]

# ======================
# CATEGORIAS / PALAVRAS-CHAVE
# ======================
CATEGORY_KEYWORDS = {
    "Trabalhista": [
        "trabalho", "trabalhista", "justica do trabalho", "justiça do trabalho",
        "trt", "tst", "vara do trabalho", "clt", "mpt", "greve", "sindicato",
        "empregado", "empregador", "verbas rescisorias", "verbas rescisórias",
        "fgts", "horas extras", "assedio eleitoral", "assédio eleitoral",
        "insalubridade", "periculosidade"
    ],
    "Jurídica": [
        "justica", "justiça", "judiciario", "judiciário", "tribunal", "juiz",
        "juiza", "juíza", "desembargador", "desembargadora", "stf", "stj",
        "cnj", "processo", "acao", "ação", "sentenca", "sentença", "acordao",
        "acórdão", "liminar", "recurso", "decisao", "decisão", "advogado"
    ],
    "Política": [
        "politica", "política", "governo", "presidente", "governador", "prefeito",
        "assembleia", "assembleia legislativa", "câmara", "camara", "senado",
        "deputado", "deputada", "senador", "senadora", "eleicao", "eleição",
        "eleitoral", "planalto", "ministro", "ministra"
    ],
    "Crime": [
        "crime", "policia", "polícia", "prisao", "prisão", "preso", "presa",
        "homicidio", "homicídio", "roubo", "furto", "trafico", "tráfico",
        "operacao", "operação", "investigacao", "investigação", "delegado",
        "delegacia", "violencia", "violência", "assassinato"
    ],
    "Economia": [
        "economia", "mercado", "inflacao", "inflação", "juros", "selic", "ibge",
        "emprego", "desemprego", "renda", "industria", "indústria", "comercio",
        "comércio", "exportacao", "exportação", "importacao", "importação",
        "orcamento", "orçamento", "fiscal", "receita", "arrecadacao", "arrecadação"
    ],
    "Agro": [
        "agro", "agronegocio", "agronegócio", "safra", "soja", "milho", "algodao",
        "algodão", "pecuaria", "pecuária", "gado", "boi", "frigorifico", "frigorífico",
        "plantio", "colheita", "produtor rural", "agricultura"
    ],
    "Cultura": [
        "cultura", "show", "festival", "cinema", "teatro", "musica", "música",
        "livro", "literatura", "exposicao", "exposição", "artista", "arte",
        "museu", "espetaculo", "espetáculo", "programacao cultural", "programação cultural"
    ],
}

GENERIC_BLOCKS = [
    "loteria", "horoscopo", "horóscopo", "bbb", "big brother", "fofoca",
    "celebridades", "receita", "receitas", "moda", "beleza", "game", "games",
]

MT_TERMS = [
    "mato grosso", "cuiaba", "cuiabá", "varzea grande", "várzea grande",
    "rondonopolis", "rondonópolis", "sinop", "sorriso", "lucas do rio verde",
    "primavera do leste", "tangara da serra", "tangará da serra",
    "alta floresta", "barra do garcas", "barra do garças",
    "caceres", "cáceres", "mt"
]

# ======================
# UTILIDADES
# ======================
def norm(s: str) -> str:
    s = s or ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()

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
        print("TELEGRAM:", r.status_code, r.text[:200])
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

def is_blocked_url(u: str) -> bool:
    try:
        p = urlparse(u)
    except Exception:
        return True

    netloc = (p.netloc or "").lower()
    full = ((p.path or "") + "?" + (p.query or "")).lower()

    for bd in BLOCKED_DOMAINS:
        bd = bd.lower()
        if netloc == bd or netloc.endswith("." + bd):
            return True

    for snip in BLOCKED_PATH_SNIPPETS:
        if snip.lower() in full:
            return True

    return False

def is_listing_url(u: str) -> bool:
    p = urlparse(u)
    netloc = (p.netloc or "").lower()
    path = (p.path or "").lower()
    qs = parse_qs(p.query or "")

    if "g1.globo.com" in netloc:
        return not path.endswith(".ghtml")

    if "olhardireto.com.br" in netloc:
        if path.rstrip("/") in ("", "/", "/juridico/noticias"):
            return True
        if path.endswith("/juridico/noticias/index.asp") and "editoria" in qs and "noticia" not in qs:
            return True

    if "gazetadigital.com.br" in netloc:
        if "/editorias/" in path and path.rstrip("/").count("/") <= 3:
            return True

    if "conjur.com.br" in netloc:
        if path.rstrip("/") in ("", "/", "/rss", "/rss/"):
            return True

    if "cpanoticias.com" in netloc:
        if path.rstrip("/") in ("", "/"):
            return True

    return False

def good_url(u: str) -> bool:
    if is_blocked_url(u):
        return False
    if is_listing_url(u):
        return False
    bad_ext = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".pdf", ".mp4", ".mp3", ".zip")
    return not u.lower().endswith(bad_ext)

def same_domain(base, u) -> bool:
    b = (urlparse(base).netloc or "").lower()
    n = (urlparse(u).netloc or "").lower()
    if not b or not n:
        return False

    if "g1.globo.com" in b:
        return "g1.globo.com" in n

    return (n == b) or n.endswith("." + b)

def clean_olhar_url(u: str) -> str:
    if "olhardireto.com.br" not in u:
        return u

    u = u.replace("¬", "")
    parsed = urlparse(u)
    qs = parse_qs(parsed.query, keep_blank_values=True)

    if "icia" in qs and "noticia" not in qs:
        qs["noticia"] = qs.pop("icia")

    new_query = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

def fetch(url: str) -> str:
    time.sleep(SLEEP)
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    return r.text

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

        if not same_domain(source_url, u):
            continue
        if not good_url(u):
            continue

        links.append(u)

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

    title = htmlmod.unescape(title or "").strip()

    article = soup.find("article")
    text = article.get_text(" ", strip=True) if article else soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    text = htmlmod.unescape(text)

    m = re.search(r"\b([01]\d|2[0-3])[:h]([0-5]\d)\b", text)
    hhmm = f"{m.group(1)}:{m.group(2)}" if m else None

    netloc = urlparse(url).netloc.lower()
    fonte = netloc
    if "g1.globo.com" in netloc:
        fonte = "G1"
    elif "portal.trt23.jus.br" in netloc:
        fonte = "TRT23"
    elif "reportermt.com" in netloc:
        fonte = "Repórter MT"
    elif "gazetadigital.com.br" in netloc:
        fonte = "Gazeta Digital"
    elif "folhamax.com" in netloc:
        fonte = "FolhaMax"
    elif "olhardireto.com.br" in netloc:
        fonte = "Olhar Direto"
    elif "conjur.com.br" in netloc:
        fonte = "ConJur"
    elif "cpanoticias.com" in netloc:
        fonte = "CPA Notícias"
    elif "poder360.com.br" in netloc:
        fonte = "Poder360"
    elif "agenciabrasil.ebc.com.br" in netloc:
        fonte = "Agência Brasil"
    elif "valor.globo.com" in netloc:
        fonte = "Valor"
    elif "cnnbrasil.com.br" in netloc:
        fonte = "CNN Brasil"
    elif "estadao.com.br" in netloc:
        fonte = "Estadão"

    return (title[:220].strip(), text, hhmm, fonte)

def detect_category(title: str, text: str) -> str | None:
    t = norm(title + " " + text)

    best_cat = None
    best_score = 0

    for category, words in CATEGORY_KEYWORDS.items():
        score = sum(1 for w in words if norm(w) in t)
        if score > best_score:
            best_score = score
            best_cat = category

    return best_cat if best_score >= 1 else None

def is_mt_news(title: str, text: str, url: str, fonte: str) -> bool:
    t = norm(title + " " + text + " " + url + " " + fonte)
    return any(norm(term) in t for term in MT_TERMS)

def is_good_article(title: str, text: str) -> bool:
    t = norm(title + " " + text)

    if not title or len(title.strip()) < 12:
        return False

    if len(text) < 250:
        return False

    if any(norm(b) in t for b in GENERIC_BLOCKS):
        return False

    return detect_category(title, text) is not None

def fmt_item(title: str, hhmm: str | None, fonte: str, url: str, n: int, categoria: str) -> str:
    safe_title = htmlmod.escape(title.strip())
    safe_url = htmlmod.escape(url)
    safe_fonte = htmlmod.escape(fonte)
    safe_cat = htmlmod.escape(categoria)

    if hhmm:
        head = f"{hhmm} - {safe_title} ({safe_fonte} | {safe_cat})"
    else:
        head = f"{safe_title} ({safe_fonte} | {safe_cat})"

    return f"{n}) {head}\n    {safe_url}\n"

def coletar_noticias(fontes, prioridade_mt: bool):
    hist = load_hist()
    relevantes = []
    analyzed = 0

    for src in fontes:
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
            if link in hist:
                continue
            if not good_url(link):
                continue

            analyzed += 1

            try:
                title, text, hhmm, fonte = get_title_text_time_source(link)
            except Exception as e:
                if DEBUG:
                    print("Falha ao abrir:", link, e)
                continue

            if not is_good_article(title, text):
                continue

            categoria = detect_category(title, text)
            if not categoria:
                continue

            eh_mt = is_mt_news(title, text, link, fonte)

            if prioridade_mt and not eh_mt:
                continue
            if not prioridade_mt and eh_mt:
                continue

            relevantes.append((title, hhmm, fonte, link, categoria))
            hist.add(link)

    save_hist(hist)
    return relevantes

# ======================
# MAIN
# ======================
def main():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    noticias_mt = coletar_noticias(SOURCES_MT, prioridade_mt=True)[:MAX_RELEVANTES_MT]
    noticias_br = coletar_noticias(SOURCES_BR, prioridade_mt=False)[:MAX_RELEVANTES_BR]

    msg = []
    msg.append(f"📅 {agora}")
    msg.append("📰 RESUMO DIÁRIO DE NOTÍCIAS")
    msg.append("")

    msg.append("📍 MATO GROSSO")
    if noticias_mt:
        for i, (title, hhmm, fonte, link, categoria) in enumerate(noticias_mt, start=1):
            msg.append(fmt_item(title, hhmm, fonte, link, i, categoria).rstrip())
    else:
        msg.append("(nenhuma notícia encontrada de Mato Grosso)")

    msg.append("")
    msg.append("🇧🇷 NACIONAL")
    if noticias_br:
        for i, (title, hhmm, fonte, link, categoria) in enumerate(noticias_br, start=1):
            msg.append(fmt_item(title, hhmm, fonte, link, i, categoria).rstrip())
    else:
        msg.append("(nenhuma notícia nacional encontrada)")

    full = "\n".join(msg).strip()

    parts = chunk_telegram(full)

    if DEBUG:
        print("Enviando Telegram (partes):", len(parts))

    for p in parts:
        telegram_send(p)

if __name__ == "__main__":
    main()
