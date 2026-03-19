import re
import json
import os
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_WHATSAPP_NUMBER")

TWILIO_CLIENT = Client(account_sid, auth_token) if all([account_sid, auth_token, TWILIO_FROM]) else None

def parse_dados(bloco: str):
    bloco = bloco.strip()
    if not bloco:
        return None

    bloco_upper = bloco.upper()
    is_alarme = "ALARME" in bloco_upper
    is_ligando = "EQUIPAMENTO_LIGANDO" in bloco_upper

    if is_ligando:
        return None

    if is_alarme and TWILIO_CLIENT:
        try:
            if '|' in bloco:
                local = bloco.rsplit('|', 1)[-1].strip()
            elif re.search(r'BIOTERIO_UFMG|UFMG', bloco_upper):
                local = "BIOTERIO_UFMG"
            elif "LAMMEBIO" in bloco_upper:
                local = "LAMMEBIO"
            else:
                local = "DESCONHECIDO"

            m_ts = re.search(r'(\d{2}/\d{2}/\d{2}_\d{2}:\d{2}:\d{2})', bloco)
            timestamp = m_ts.group(1) if m_ts else ""

            var1 = f"{local} - {bloco[:120]}"
            var2 = timestamp

            TWILIO_CLIENT.messages.create(
                from_=TWILIO_FROM,
                to="whatsapp:+5561999182112",
                content_sid="HX4aa31c6e5385f78336c83cde97dfac24",
                content_variables=json.dumps({"1": var1, "2": var2})
            )
        except:
            pass

    if '|' in bloco:
        local = bloco.rsplit('|', 1)[-1].strip()
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
        "Alarme": "SIM" if is_alarme else "Não",
        "Alarme_Detalhe": bloco if is_alarme else "",
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

        m_luz = re.search(rf'SL{i}_(?:CLARO|ESCURO)([^@|]*?)(?=@SL{i}_|@|\Z)', bloco, re.IGNORECASE)
        if m_luz:
            raw = m_luz.group(0).strip()
            status = re.search(r'(CLARO|ESCURO)', raw, re.IGNORECASE)
            dados[f"SL{i}_Luz"] = status.group(1).upper() if status else ""
            if '_F' in raw.upper():
                dados["Falhas_SL"][f"SL{i}_Luz"] = True

    return dados