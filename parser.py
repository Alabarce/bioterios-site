import re

def parse_dados(bloco: str) -> dict:
    bloco = bloco.strip()
    bloco_upper = bloco.upper()

    local = ""
    if '|' in bloco:
        local = bloco.rsplit('|', 1)[-1].strip()
    else:
        if re.search(r'BIOTERIO_UFMG|UFMG', bloco_upper):
            local = "BIOTERIO_UFMG"
        elif re.search(r'LAMMEBIO', bloco_upper):
            local = "LAMMEBIO"
        else:
            local = "DESCONHECIDO"

    dados = {
        "Timestamp": "",
        "Local": local,
        "Sensor_ID": "",
        "Sinal": "",
        "VBAT": "",
        "Energia": "",
        "Alarme": "Não",
        "Alarme_Detalhe": "",
        "Falhas_SL": {}
    }

    # Extrai timestamp sempre
    m_ts = re.search(r'(\d{2}/\d{2}/\d{2}_\d{2}:\d{2}:\d{2})', bloco)
    if m_ts:
        dados["Timestamp"] = m_ts.group(1)

    # Se tiver ALARME no bloco inteiro, captura detalhe após o segundo @
    if 'ALARME' in bloco_upper:
        dados["Alarme"] = "SIM"
        partes = bloco.split('@')
        if len(partes) >= 3:
            detalhe = '@'.join(partes[2:]).split('|')[0].strip()
            dados["Alarme_Detalhe"] = detalhe
        else:
            dados["Alarme_Detalhe"] = "ALARME DETECTADO"

    # Extrai Sensor_ID, Sinal, VBAT, Energia (mesmo sem ID numérico inicial)
    partes = [p.strip() for p in bloco.split('@') if p.strip()]
    if len(partes) >= 5:
        # Sensor_ID: primeiro campo numérico longo após timestamp
        m_sensor = re.search(r'@(\d{4,6})@', bloco)
        if m_sensor:
            dados["Sensor_ID"] = m_sensor.group(1)

        # Sinal, VBAT, Energia: campos 3,4,5 após timestamp (ajustado pro novo formato)
        if len(partes) >= 6:
            dados["Sinal"] = partes[2] if len(partes) > 2 else ""
            dados["VBAT"] = partes[3] if len(partes) > 3 else ""
            dados["Energia"] = partes[4] if len(partes) > 4 else ""

    # Extrai SLx_ (T, RH, Luz)
    resto = bloco
    for i in range(1, 9):
        m_t_raw = re.search(rf'SL{i}_T:([^@|]+?)(?=@SL{i}_|@|\Z)', resto, re.IGNORECASE)
        if m_t_raw:
            raw_t = m_t_raw.group(1).strip()
            valor_t = re.match(r'([\d.]+C?)', raw_t).group(1) if re.match(r'([\d.]+C?)', raw_t) else ""
            dados[f"SL{i}_T"] = valor_t

        m_rh_raw = re.search(rf'SL{i}_RH:([^@|]+?)(?=@SL{i}_|@|\Z)', resto, re.IGNORECASE)
        if m_rh_raw:
            raw_rh = m_rh_raw.group(1).strip()
            valor_rh = re.match(r'([\d.]+%?)', raw_rh).group(1) if re.match(r'([\d.]+%?)', raw_rh) else ""
            dados[f"SL{i}_RH"] = valor_rh

        m_luz_raw = re.search(rf'SL{i}_(?:CLARO|ESCURO)([^@|]*?)(?=@SL{i}_|@|\Z)', resto, re.IGNORECASE)
        if m_luz_raw:
            raw_luz = m_luz_raw.group(0).strip()
            valor_luz = re.search(r'(CLARO|ESCURO)', raw_luz, re.IGNORECASE).group(1).upper() if re.search(r'(CLARO|ESCURO)', raw_luz, re.IGNORECASE) else ""
            dados[f"SL{i}_Luz"] = valor_luz

    return dados