import os
import json
import time
import re
import html
import unicodedata
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
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
MAX_PAGINAS_ANALISADAS = int(os.getenv("MAX_PAGINAS_ANALISADAS", "220"))

MAX_RELEVANTES = int(os.getenv("MAX_RELEVANTES", "12"))

# mais rígido
STRICT_JT = os.getenv("STRICT_JT", "1") == "1"

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise SystemExit("ERRO: Defina TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no ambiente.")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) TelegramNewsBot/1.0",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# ======================
# FONTES (sem CNJ)
# ======================
SOURCES = [
    # TRT23
    "https://portal.trt23.jus.br/portal/noticias",
    "https://portal.trt23.jus.br/portal/noticias?page=1",

    # Portais (só entra se bater keywords)
    "https://g1.globo.com/mt/mato-grosso/",
    "https://www.olhardireto.com.br/juridico/",
    "https://www.reportermt.com/ultimas-noticias",
    "https://www.gazetadigital.com.br/editorias/judiciario/",
    "https://www.folhamax.com/",
    "https://www.tjmt.jus.br/noticias",
    "https://www.estadaomatogrosso.com.br",

    # Pedidas
    "https://lucasdorioverde.portaldacidade.com/",
    "https://www.conjur.com.br/",
    "https://cpanoticias.com/",
]

# ======================
# BLOQUEIOS (agressivo)
# ======================
BLOCKED_DOMAINS = {
    "globoplay.globo.com",
    "ge.globo.com",
    "gshow.globo.com",
    "valor.globo.com",
    "oglobo.globo.com",
    "extra.globo.com",
    "cnj.jus.br",
}

BLOCKED_PATH_SNIPPETS = [
    # mídia / landing
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

    # corta cursos/concursos
    "cursos-e-concursos", "curso", "concursos", "concurso",

    # TRT23 (menus/páginas institucionais que o crawler pega muito)
    "/portal/menulistchildren/",
    "/portal/o-trt",
    "/portal/composicao-do-trt",
    "/portal/corregedoria",
    "/portal/ejud",
    "/portal/foros-trabalhistas",
    "/portal/gestao-estrategica",
    "/portal/juizes-do-trabalho",
    "/portal/memorial",
    "/portal/pontos-de-inclusao-digital",
    "/portal/programas-acoes-e-projetos",
    "/portal/sustentabilidade",
    "/portal/varas-do-trabalho",
    "/portal/servicos",
    "/portal/biblioteca",
    "/portal/reports/",
]

# ======================
# FILTRO: Justiça do Trabalho (contexto)
# ======================
JT_CONTEXT = [
    "justiça do trabalho", "justica do trabalho",
    "trabalh",  # trabalhista, trabalhador etc.
    "trt", "trt23", "trt-23", "trtmt",
    "tst", "clt",
    "vara do trabalho", "varas do trabalho",
    "mpt", "ministerio publico do trabalho", "ministério público do trabalho",
]

def norm(s: str) -> str:
    s = s or ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()

def has_jt_context(title: str, text: str) -> bool:
    t = norm(title + " " + text)
    return any(norm(k) in t for k in JT_CONTEXT)

# ======================
# FILTRO: suas keywords (mais preciso)
# - frases específicas passam
# - termos soltos só passam com contexto JT
# ======================
KEY_STRICT_PHRASES = [
    "processo trabalhista", "processos trabalhistas",
    "acao trabalhista", "acoes trabalhistas",
    "ação trabalhista", "ações trabalhistas",
    "reclamacao trabalhista", "reclamacoes trabalhistas",
    "reclamação trabalhista", "reclamações trabalhistas",
    "decisao trabalhista", "decisoes trabalhistas",
    "decisão trabalhista", "decisões trabalhistas",
    "sentenca trabalhista", "sentencas trabalhistas",
    "sentença trabalhista", "sentenças trabalhistas",
    "condenacao trabalhista", "condenacoes trabalhistas",
    "condenação trabalhista", "condenações trabalhistas",
    "indenizacao trabalhista", "indenizacoes trabalhistas",
    "indenização trabalhista", "indenizações trabalhistas",
    "danos morais trabalhistas", "dano moral trabalhista",
    "acordo em processo trabalhista", "acordos em processos trabalhistas",
    "cumprimento de sentenca", "cumprimento de sentença",
    "cumprimento de sentencas", "cumprimento de sentenças",
    "execucao de processo trabalhista", "execução de processo trabalhista",
    "execucoes de processos trabalhistas", "execuções de processos trabalhistas",
    "penhoras de empresas", "penhora de empresa",
    "bloqueios de bens", "bloqueio de bens",
    "audiencia trabalhista", "audiência trabalhista",
    "audiencias trabalhistas", "audiências trabalhistas",
    "embargos trabalhistas", "embargo trabalhista",
    "inquerito trabalhista", "inquérito trabalhista",
    "inqueritos trabalhistas", "inquéritos trabalhistas",
]

# termos soltos: só valem se houver contexto JT também
KEY_SINGLE_TERMS = [
    "liminar", "tutela",
    "acordao", "acórdão", "acordaos", "acórdãos",
    "recurso", "recursos",
    "agravo", "agravos",
    "homologacao", "homologação", "homologacoes", "homologações",
]

def has_required_keywords(title: str, text: str) -> bool:
    t = norm(title + " " + text)

    # 1) frases específicas
    for ph in KEY_STRICT_PHRASES:
        if norm(ph) in t:
            return True

    # 2) termos soltos só com contexto JT
    if not has_jt_context(title, text):
        return False

    for w in KEY_SINGLE_TERMS:
        if norm(w) in t:
            return True

    return False

def is_target_article(title: str, text: str) -> bool:
    if not has_required_keywords(title, text):
        return False
    # endurece: exige contexto JT
    if STRICT_JT:
        return has_jt_context(title, text)
    return True

# ======================
# UTILIDADES: bloqueio + "cara de matéria"
# ======================
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

def looks_like_article_url(u: str) -> bool:
    """
    Mata páginas índice/categoria (igual as que apareceram no seu print).
    Regras por domínio (simples e eficientes).
    """
    p = urlparse(u)
    netloc = (p.netloc or "").lower()
    path = (p.path or "").lower()
    query = (p.query or "").lower()

    # TRT23: matéria costuma estar em /portal/noticias/<slug>
    if "portal.trt23.jus.br" in netloc:
        return "/portal/noticias/" in path and not path.rstrip("/").endswith("/portal/noticias")

    # G1: notícia é /noticia/... .ghtml
    if "g1.globo.com" in netloc:
        return ("/noticia/" in path) and path.endswith(".ghtml")

    # Olhar (jurídico): notícia é exibir.asp?id=...&noticia=...
    if "olhardireto.com.br" in netloc:
        if "exibir.asp" in path and "id=" in query:
            return True
        return False  # corta /juridico/noticias/ e index.asp?id=...

    # RepórterMT: geralmente termina com /<id>
    if "reportermt.com" in netloc:
        return bool(re.search(r"/\d{3,}$", path))

    # Gazeta Digital: matérias costumam terminar com /<id>
    if "gazetadigital.com.br" in netloc:
        return bool(re.search(r"/\d{3,}$", path))

    # FolhaMax: termina com /<id>
    if "folhamax.com" in netloc:
        return bool(re.search(r"/\d{3,}$", path))

    # TJMT / Estadão MT / ConJur / Portal da Cidade / CPA: não dá pra padronizar 100%,
    # então só corta óbvias "home/índice"
    if path in ("/", ""):
        return False
    if path.endswith("/noticias/") or path.endswith("/noticias"):
        return False
    return True

def good_url(u: str) -> bool:
    if is_blocked_url(u):
        return False
    bad_ext = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".pdf", ".mp4", ".mp3", ".zip")
    return not u.lower().endswith(bad_ext)

def same_domain(base, u) -> bool:
    b = (urlparse(base).netloc or "").lower()
    n = (urlparse(u).netloc or "").lower()
    if not b or not n:
        return False

    # G1: só permite continuar no próprio g1
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

        if not good_url(u):
            continue
        if not same_domain(source_url, u):
            continue
        if not looks_like_article_url(u):
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

    article = soup.find("article")
    text = article.get_text(" ", strip=True) if article else soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()

    m = re.search(r"\b([01]\d|2[0-3])[:h]([0-5]\d)\b", text)
    hhmm = f"{m.group(1)}:{m.group(2)}" if m else None

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
    elif "conjur.com.br" in netloc:
        fonte = "ConJur"
    elif "portaldacidade.com" in netloc:
        fonte = "Portal da Cidade"
    elif "cpanoticias.com" in netloc:
        fonte = "CPA Notícias"

    return (title[:220].strip(), text, hhmm, fonte)

def fmt_item(title: str, hhmm: str | None, fonte: str, url: str, n: int) -> str:
    safe_title = html.escape(title.strip())
    safe_url = html.escape(url)
    if hhmm:
        head = f"{hhmm} - {safe_title} ({html.escape(fonte)})"
    else:
        head = f"{safe_title} ({html.escape(fonte)})"
    return f"{n}) {head}\n    {safe_url}\n"

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

# ======================
# MAIN
# ======================
def main():
    hist = load_hist()
    agora = datetime.now(ZoneInfo("America/Cuiaba")).strftime("%d/%m/%Y %H:%M")

    relevantes = []
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
            if link in hist:
                continue
            if not good_url(link):
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

            # evita lixo
            if not title or len(text) < 300:
                continue

            # >>> SOMENTE SUAS KEYWORDS + CONTEXTO JT <<<
            if not is_target_article(title, text):
                continue

            relevantes.append((title, hhmm, fonte, link))
            hist.add(link)

            if len(relevantes) >= MAX_RELEVANTES:
                break

    save_hist(hist)

    msg = []
    msg.append(f"📅 {agora}")
    msg.append("⚖️ NOTICIAS RELEVANTES PARA O TRT23")
    msg.append("")
    msg.append("RELEVANTES TRT23:")

    if relevantes:
        for i, (title, hhmm, fonte, link) in enumerate(relevantes[:MAX_RELEVANTES], start=1):
            msg.append(fmt_item(title, hhmm, fonte, link, n=i).rstrip())
    else:
        msg.append("(nenhuma notícia encontrada com seus termos de processo/decisão trabalhista)")

    full = "\n".join(msg).strip()

    parts = chunk_telegram(full)
    if DEBUG:
        print("Enviando Telegram (partes):", len(parts))

    for p in parts:
        telegram_send(p)

if __name__ == "__main__":
    main()
