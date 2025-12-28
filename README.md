# Bot Telegram – Notícias (Justiça do Trabalho/TRT23)

Bot em Python que varre fontes selecionadas e envia para o Telegram **somente notícias de Justiça do Trabalho**
que contenham **palavras-chave específicas sobre processo/decisão trabalhista**.

## O que ele envia
Formato:
- 📅 data/hora
- ⚖️ NOTICIAS RELEVANTES PARA O TRT23
- RELEVANTES TRT23:
  - (lista numerada com título, hora quando existir, fonte e link)

## Fontes
- TRT23 (portal)
- G1 MT (somente links .ghtml)
- Olhar Direto Jurídico (somente matérias)
- Repórter MT (ultimas)
- Gazeta Digital (Judiciário)
- FolhaMax
- Portal da Cidade (Lucas do Rio Verde)
- ConJur
- CPA Notícias

## Palavras-chave (filtro)
O bot só envia se encontrar termos como:
- processo trabalhista / ação trabalhista / reclamação trabalhista
- decisão/sentença trabalhista
- condenação/indenização trabalhista / danos morais trabalhista
- liminar / tutela / acórdão / recurso / agravo
- execução / penhora / bloqueio de bens
- acordo/homologação / cumprimento de sentença
- inquérito trabalhista

E também exige **contexto trabalhista** (TRT/TST/CLT/vara do trabalho etc).

## Como rodar local
Windows PowerShell:

```powershell
$env:TELEGRAM_TOKEN="SEU_TOKEN"
$env:TELEGRAM_CHAT_ID="SEU_CHAT_ID"
$env:DEBUG="1"
python -m pip install -r requirements.txt
python main.py
