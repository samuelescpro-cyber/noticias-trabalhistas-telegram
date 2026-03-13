# Bot Telegram – Resumo Diário de Notícias

Bot em Python que coleta notícias de fontes selecionadas e envia para o Telegram um **resumo diário**, com prioridade para:

1. **Mato Grosso**
2. **Nacional**

O bot tenta identificar notícias das seguintes áreas:
- trabalhista
- jurídica
- política
- crime
- economia
- agro
- cultura

## O que ele envia

Formato da mensagem:
- 📅 data/hora
- 📰 RESUMO DIÁRIO DE NOTÍCIAS
- 📍 MATO GROSSO
  - lista numerada com título, hora quando existir, fonte, categoria e link
- 🇧🇷 NACIONAL
  - lista numerada com título, hora quando existir, fonte, categoria e link

## Ordem de prioridade

O envio segue esta lógica:
- primeiro notícias de **Mato Grosso**
- depois notícias **nacionais**

## Categorias identificadas

O bot classifica as matérias com base em palavras encontradas no título e no texto.

### Trabalhhista
Exemplos:
- trabalho
- trabalhista
- Justiça do Trabalho
- TRT
- TST
- CLT
- sindicato
- greve
- FGTS
- horas extras

### Jurídica
Exemplos:
- Justiça
- Judiciário
- tribunal
- juiz
- juíza
- sentença
- liminar
- recurso
- decisão
- processo

### Política
Exemplos:
- governo
- presidente
- governador
- prefeito
- câmara
- senado
- deputado
- eleição
- ministro

### Crime
Exemplos:
- polícia
- prisão
- homicídio
- roubo
- tráfico
- operação
- investigação
- violência

### Economia
Exemplos:
- economia
- mercado
- inflação
- juros
- Selic
- emprego
- renda
- comércio
- arrecadação

### Agro
Exemplos:
- agronegócio
- safra
- soja
- milho
- algodão
- pecuária
- gado
- frigorífico
- agricultura

### Cultura
Exemplos:
- cultura
- show
- festival
- cinema
- teatro
- música
- livro
- exposição
- artista

## Fontes

### Mato Grosso
- TRT23
- G1 Mato Grosso
- Olhar Direto
- Repórter MT
- Gazeta Digital
- FolhaMax
- CPA Notícias

### Nacional
- G1
- ConJur
- Poder360
- Agência Brasil
- Valor
- CNN Brasil
- Estadão

## Regras do bot

O bot:
- evita links repetidos usando o arquivo `enviadas.json`
- ignora páginas de vídeo, galeria, login, tag, podcasts e páginas institucionais
- tenta filtrar páginas que não sejam notícia
- só envia links ainda não disparados antes

## Arquivos do projeto

- `main.py` → código principal do bot
- `enviadas.json` → histórico de links já enviados
- `requirements.txt` → dependências
- `.github/workflows/noticia.yml` → agendamento no GitHub Actions

## Variáveis de ambiente

Defina estas variáveis:

- `TELEGRAM_TOKEN` → token do bot
- `TELEGRAM_CHAT_ID` → ID do chat ou canal
- `DEBUG` → `1` para mostrar logs, `0` para modo normal
- `SLEEP` → intervalo entre requisições
- `MAX_LINKS_POR_FONTE` → máximo de links coletados por site
- `MAX_PAGINAS_ANALISADAS` → máximo de páginas abertas por execução
- `MAX_RELEVANTES_MT` → quantidade máxima de notícias de Mato Grosso
- `MAX_RELEVANTES_BR` → quantidade máxima de notícias nacionais

## Como rodar localmente

### Windows PowerShell

```powershell
$env:TELEGRAM_TOKEN="SEU_TOKEN"
$env:TELEGRAM_CHAT_ID="SEU_CHAT_ID"
$env:DEBUG="1"
python -m pip install -r requirements.txt
python main.py
