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
        "Alarme": "SIM" if re.search(r'ALARME|ALERT|EQUIPAMENTO_LIGANDO', bloco_upper) else "Não",
        "Falhas_SL": {}
    }

    partes = [p.strip() for p in bloco.split('@') if p.strip()]

    if len(partes) >= 5 and re.match(r'^\d{4,6}$', partes[0]):
        dados["Sensor_ID"] = partes[0]
        dados["Timestamp"] = partes[1]
        dados["Sinal"] = partes[2]
        dados["VBAT"] = partes[3]
        dados["Energia"] = partes[4]

        if '|' in bloco:
            resto = bloco.rsplit('|', 1)[0].strip()
        else:
            resto = bloco

        for i in range(1, 9):
            m_t_raw = re.search(rf'SL{i}_T:([^@|]+?)(?=@SL{i}_|@|\Z)', resto, re.IGNORECASE)
            if m_t_raw:
                raw_t = m_t_raw.group(1).strip()
                valor_t = re.match(r'([\d.]+C?)', raw_t).group(1) if re.match(r'([\d.]+C?)', raw_t) else ""
                dados[f"SL{i}_T"] = valor_t
                dados["Falhas_SL"][f"SL{i}_T"] = "_F" in raw_t.upper()

            m_rh_raw = re.search(rf'SL{i}_RH:([^@|]+?)(?=@SL{i}_|@|\Z)', resto, re.IGNORECASE)
            if m_rh_raw:
                raw_rh = m_rh_raw.group(1).strip()
                valor_rh = re.match(r'([\d.]+%?)', raw_rh).group(1) if re.match(r'([\d.]+%?)', raw_rh) else ""
                dados[f"SL{i}_RH"] = valor_rh
                dados["Falhas_SL"][f"SL{i}_RH"] = "_F" in raw_rh.upper()

            m_luz_raw = re.search(rf'SL{i}_(?:CLARO|ESCURO)([^@|]*?)(?=@SL{i}_|@|\Z)', resto, re.IGNORECASE)
            if m_luz_raw:
                raw_luz = m_luz_raw.group(0).strip()
                valor_luz = re.search(r'(CLARO|ESCURO)', raw_luz, re.IGNORECASE).group(1).upper() if re.search(r'(CLARO|ESCURO)', raw_luz, re.IGNORECASE) else ""
                dados[f"SL{i}_Luz"] = valor_luz
                dados["Falhas_SL"][f"SL{i}_Luz"] = "_F" in raw_luz.upper()

    if dados["Alarme"] == "SIM" and not dados["Timestamp"]:
        m_ts = re.search(r'(\d{2}/\d{2}/\d{2}_\d{2}:\d{2}:\d{2})', bloco)
        if m_ts:
            dados["Timestamp"] = m_ts.group(1)

    return dados