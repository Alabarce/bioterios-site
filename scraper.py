import requests
import sqlite3
import re
import time
from datetime import datetime
from parser import parse_dados
from database import salvar, ja_processado

URL = "https://i9biotech.com.br/monitor_bioterios/index.php?op=4"
INTERVALO_MINUTOS = 4

def limpar_texto_html(texto):
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'<[^>]+>', '', texto)
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    return '\n'.join(linhas)

def extrair_mensagens():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(URL, timeout=15, headers=headers)
        r.raise_for_status()
    except Exception as e:
        print(f"[{datetime.now()}] Erro ao acessar i9biotech: {e}")
        return []
    texto_limpo = limpar_texto_html(r.text)
    linhas = texto_limpo.splitlines()
    mensagens = []
    for linha in reversed(linhas[-80:]):
        linha = linha.strip()
        if not linha:
            continue
        if '@' in linha or 'EQUIPAMENTO_LIGANDO' in linha.upper() or 'ALARME' in linha.upper():
            mensagens.append(linha)
    return list(dict.fromkeys(mensagens))

def rodar_scraper():
    print(f"[{datetime.now()}] Scraper iniciado em background")
    while True:
        mensagens = extrair_mensagens()
        novas = 0
        for bloco in mensagens:
            dados = parse_dados(bloco)
            timestamp = dados.get("Timestamp", "")
            sensor_id = dados.get("Sensor_ID", "")
            local = dados.get("Local", "")
            if not timestamp or not sensor_id:
                continue
            if ja_processado(timestamp, sensor_id, local):
                break
            salvar(dados, bloco)
            novas += 1
            try:
                requests.post("http://127.0.0.1:8000/api/receber", data=bloco, headers={"Content-Type": "text/plain"}, timeout=10)
            except:
                pass
        print(f"[{datetime.now()}] Scraper: {novas} novas mensagens processadas")
        time.sleep(INTERVALO_MINUTOS * 60)
