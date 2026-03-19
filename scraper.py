import requests
import re
import time
from parser import parse_dados
from database import salvar, DB
import sqlite3

URL = "https://i9biotech.com.br/monitor_bioterios/index.php?op=4"
INTERVALO_MINUTOS = 2

def limpar_texto_html(texto):
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'<[^>]+>', '', texto)
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    return '\n'.join(linhas)

def processar_bloco_novo(conn, bloco):
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM leituras WHERE raw_bloco = ?", (bloco,))
    if cursor.fetchone() is None:
        dados = parse_dados(bloco)
        if not dados:
            return
        salvar(dados, bloco)
        try:
            requests.post("http://127.0.0.1:8000/api/receber", data=bloco, headers={"Content-Type": "text/plain"}, timeout=10)
        except:
            pass

def rodar_scraper():
    conn = sqlite3.connect(DB)
    while True:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(URL, timeout=15, headers=headers)
            r.raise_for_status()

            texto_limpo = limpar_texto_html(r.text)
            linhas = texto_limpo.splitlines()

            for linha in reversed(linhas[-50:]):
                bloco = linha.strip()
                if not bloco:
                    continue
                if not ('@' in bloco or 'ALARME' in bloco.upper() or 'EQUIPAMENTO_LIGANDO' in bloco.upper()):
                    continue
                processar_bloco_novo(conn, bloco)

        except:
            pass

        time.sleep(INTERVALO_MINUTOS * 60)