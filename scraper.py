import requests
import re
import time
from datetime import datetime
from parser import parse_dados
from database import salvar, ja_processado, ja_enviado_alarme, registrar_alarme_enviado

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
    except:
        return []
    texto_limpo = limpar_texto_html(r.text)
    linhas = texto_limpo.splitlines()
    mensagens = []
    for linha in reversed(linhas[-150:]):
        linha = linha.strip()
        if linha and ('@' in linha or 'ALARME' in linha.upper() or 'EQUIPAMENTO_LIGANDO' in linha.upper()):
            mensagens.append(linha)
    return list(dict.fromkeys(mensagens))

def rodar_scraper():
    while True:
        mensagens = extrair_mensagens()
        novas = 0
        for bloco in mensagens:
            bloco = bloco.strip()
            
            is_alarme = 'ALARME' in bloco.upper() or 'EQUIPAMENTO_LIGANDO' in bloco.upper()
            
            if is_alarme:
                local = "LAMMEBIO" if "LAMMEBIO" in bloco.upper() else "BIOTERIO_UFMG" if "UFMG" in bloco.upper() else "DESCONHECIDO"
                if ja_enviado_alarme(local, bloco):
                    continue
                registrar_alarme_enviado(local, bloco, "")
            
            dados = parse_dados(bloco)
            if not dados:
                continue

            if dados.get("Alarme") == "SIM":
                local = dados.get("Local", "")
                alarme_detalhe = dados.get("Alarme_Detalhe", "")
                if alarme_detalhe and ja_enviado_alarme(local, alarme_detalhe):
                    continue
                registrar_alarme_enviado(local, alarme_detalhe, dados.get("Timestamp", ""))
            else:
                timestamp = dados.get("Timestamp", "")
                sensor_id = dados.get("Sensor_ID", "")
                if not timestamp or not sensor_id or ja_processado(timestamp, sensor_id, local):
                    continue

            salvar(dados, bloco)
            novas += 1
            try:
                requests.post("http://127.0.0.1:8000/api/receber", data=bloco, headers={"Content-Type": "text/plain"}, timeout=10)
            except:
                pass

        time.sleep(INTERVALO_MINUTOS * 60)