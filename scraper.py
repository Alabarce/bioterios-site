import requests
import re
import time
from datetime import datetime
from parser import parse_dados
from database import salvar

URL = "https://i9biotech.com.br/monitor_bioterios/index.php?op=4"
INTERVALO_MINUTOS = 2

def limpar_texto_html(texto):
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'<[^>]+>', '', texto)
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    return '\n'.join(linhas)

def ja_existe_no_banco(raw_bloco):
    import sqlite3
    from database import DB
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM leituras WHERE raw_bloco = ?", (raw_bloco,))
    existe = c.fetchone()[0] > 0
    conn.close()
    return existe

def rodar_scraper():
    print(f"[{datetime.now()}] Scraper iniciado em background")
    while True:
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            r = requests.get(URL, timeout=15, headers=headers)
            r.raise_for_status()
        except:
            time.sleep(INTERVALO_MINUTOS * 60)
            continue

        texto_limpo = limpar_texto_html(r.text)
        linhas = texto_limpo.splitlines()
        novas = 0

        for linha in reversed(linhas[-150:]):
            bloco = linha.strip()
            if not bloco:
                continue
            if not ('@' in bloco or 'ALARME' in bloco.upper() or 'EQUIPAMENTO_LIGANDO' in bloco.upper()):
                continue

            if ja_existe_no_banco(bloco):
                continue

            dados = parse_dados(bloco)
            if not dados:
                continue

            salvar(dados, bloco)
            novas += 1
            try:
                requests.post("http://127.0.0.1:8000/api/receber", data=bloco, headers={"Content-Type": "text/plain"}, timeout=10)
            except:
                pass

        print(f"[{datetime.now()}] Scraper: {novas} novas mensagens processadas")
        time.sleep(INTERVALO_MINUTOS * 60)