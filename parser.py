import re
import json
import os
import sqlite3
from dotenv import load_dotenv
from twilio.rest import Client
from database import registrar_raw_bloco, DB
load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_WHATSAPP_NUMBER")

TWILIO_CLIENT = Client(account_sid, auth_token) if all([account_sid, auth_token, TWILIO_FROM]) else None

def enviar_sms_para_grupo(local, var1, var2):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT telefone FROM usuarios WHERE ativo = 1 AND bioterios LIKE ? AND telefone IS NOT NULL", ('%' + local + '%',))
    usuarios = c.fetchall()
    conn.close()

    if not TWILIO_CLIENT:
        return
    for row in usuarios:
        telefone = row[0]
        if telefone:
            try:
                TWILIO_CLIENT.messages.create(
                    from_=TWILIO_FROM,
                    to=telefone,
                    content_sid="HX4aa31c6e5385f78336c83cde97dfac24",
                    content_variables=json.dumps({"1": var1, "2": var2})
                )
            except:
                pass



def parse_dados(bloco: str):
    # recebe a string do scraper/postman
    bloco = bloco.strip()
    if not bloco:
        return None

    bloco_upper = bloco.upper()

    # ->se detecta LIGANDO: pass/terminafunção
    if "EQUIPAMENTO_LIGANDO" in bloco_upper:
        return None

    # ->se detecta ALARME:
    is_alarme = "ALARME" in bloco_upper
    if is_alarme:
        # ->verifica se o raw_bloco tem duplicatas
        if not registrar_raw_bloco(bloco):
            return None  # caso sim, termina a função parse_dados

        # -> DETECTA LOCAL (última parte da string)
        if '|' in bloco:
            parts = [p.strip() for p in bloco.split('|') if p.strip()]
            local = parts[-1] if parts else "DESCONHECIDO"
        elif re.search(r'BIOTERIO_UFMG|UFMG', bloco_upper):
            local = "BIOTERIO_UFMG"
        elif "LAMMEBIO" in bloco_upper:
            local = "LAMMEBIO"
        else:
            local = "DESCONHECIDO"

        # -> faz a função para jogar o json para o twilio, isolando as variáveis, para usuarios cadastrados em LOCAL DETECTADO no passo acima
        m_ts = re.search(r'(\d{2}/\d{2}/\d{2}_\d{2}:\d{2}:\d{2})', bloco)
        timestamp = m_ts.group(1) if m_ts else ""
        var1 = f"{local} - {bloco[:150]}"
        var2 = timestamp
        enviar_sms_para_grupo(local, var1, var2)

        return None  # alarme tratado → não salva na leituras (não aparece no histórico/export)

    # ->else (não alarme/ligandoequipamento)
    # processa os dados como está agora
    if not registrar_raw_bloco(bloco):
        return None

    # extração do local para leituras normais
    if '|' in bloco:
        parts = [p.strip() for p in bloco.split('|') if p.strip()]
        local = parts[-1] if parts else "DESCONHECIDO"
    elif re.search(r'BIOTERIO_UFMG|UFMG', bloco_upper):
        local = "BIOTERIO_UFMG"
    elif "LAMMEBIO" in bloco_upper:
        local = "LAMMEBIO"
    else:
        local = "DESCONHECIDO"

    m_ts = re.search(r'(\d{2}/\d{2}/\d{2}_\d{2}:\d{2}:\d{2})', bloco)
    timestamp = m_ts.group(1) if m_ts else ""

    dados = {
        "Timestamp": timestamp,
        "Local": local,
        "Sensor_ID": "",
        "Sinal": "",
        "VBAT": "",
        "Energia": "",
        "Alarme": "Não",
        "Alarme_Detalhe": "",
        "Falhas_SL": {},
        "SL1_T": "", "SL1_RH": "", "SL1_Luz": "",
        "SL2_T": "", "SL2_RH": "", "SL2_Luz": "",
        "SL3_T": "", "SL3_RH": "", "SL3_Luz": "",
        "SL4_T": "", "SL4_RH": "", "SL4_Luz": "",
        "SL5_T": "", "SL5_RH": "", "SL5_Luz": "",
        "SL6_T": "", "SL6_RH": "", "SL6_Luz": "",
        "SL7_T": "", "SL7_RH": "", "SL7_Luz": "",
        "SL8_T": "", "SL8_RH": "", "SL8_Luz": ""
    }

    m_id = re.search(r'^(\d{4,6})@', bloco) or re.search(r'@(\d{4,6})@', bloco)
    if m_id:
        dados["Sensor_ID"] = m_id.group(1)

    partes = [p.strip() for p in bloco.split('@') if p.strip()]
    for p in partes:
        p_upper = p.upper()
        if p_upper.startswith('SINAL_'):
            dados["Sinal"] = p
        elif p_upper.startswith('VBAT_'):
            dados["VBAT"] = p
        elif p_upper.startswith('ENERGIA_'):
            dados["Energia"] = p

    for i in range(1, 9):
        m_t = re.search(rf'SL{i}_T:([^@|]+?)(?=@SL{i}_|@|\Z)', bloco, re.IGNORECASE)
        if m_t:
            raw = m_t.group(1).strip()
            valor = re.search(r'([\d.]+)', raw)
            dados[f"SL{i}_T"] = valor.group(1) if valor else raw
            if '_F' in raw.upper():
                dados["Falhas_SL"][f"SL{i}_T"] = True

        m_rh = re.search(rf'SL{i}_RH:([^@|]+?)(?=@SL{i}_|@|\Z)', bloco, re.IGNORECASE)
        if m_rh:
            raw = m_rh.group(1).strip()
            valor = re.search(r'([\d.]+)', raw)
            dados[f"SL{i}_RH"] = valor.group(1) if valor else raw
            if '_F' in raw.upper():
                dados["Falhas_SL"][f"SL{i}_RH"] = True

        m_luz = re.search(rf'SL{i}_(?:CLARO|ESCURO)', bloco, re.IGNORECASE)
        if m_luz:
            raw = m_luz.group(0).strip()
            status = re.search(r'(CLARO|ESCURO)', raw, re.IGNORECASE)
            dados[f"SL{i}_Luz"] = status.group(1).upper() if status else ""
            if '_F' in raw.upper():
                dados["Falhas_SL"][f"SL{i}_Luz"] = True

    return dados