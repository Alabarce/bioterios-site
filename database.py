import sqlite3
from datetime import datetime
from passlib.context import CryptContext


DB = "leituras.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS leituras (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            data_captura    TEXT NOT NULL,
            Timestamp       TEXT,
            Local           TEXT,
            Sensor_ID       TEXT,
            Sinal           TEXT,
            VBAT            TEXT,
            Energia         TEXT,
            Alarme          TEXT DEFAULT 'Não',
            Alarme_Detalhe  TEXT,
            SL1_T           TEXT, SL1_RH TEXT, SL1_Luz TEXT,
            SL2_T           TEXT, SL2_RH TEXT, SL2_Luz TEXT,
            SL3_T           TEXT, SL3_RH TEXT, SL3_Luz TEXT,
            SL4_T           TEXT, SL4_RH TEXT, SL4_Luz TEXT,
            SL5_T           TEXT, SL5_RH TEXT, SL5_Luz TEXT,
            SL6_T           TEXT, SL6_RH TEXT, SL6_Luz TEXT,
            SL7_T           TEXT, SL7_RH TEXT, SL7_Luz TEXT,
            SL8_T           TEXT, SL8_RH TEXT, SL8_Luz TEXT,
            Falha_SL1_T     INTEGER DEFAULT 0, Falha_SL1_RH INTEGER DEFAULT 0, Falha_SL1_Luz INTEGER DEFAULT 0,
            Falha_SL2_T     INTEGER DEFAULT 0, Falha_SL2_RH INTEGER DEFAULT 0, Falha_SL2_Luz INTEGER DEFAULT 0,
            Falha_SL3_T     INTEGER DEFAULT 0, Falha_SL3_RH INTEGER DEFAULT 0, Falha_SL3_Luz INTEGER DEFAULT 0,
            Falha_SL4_T     INTEGER DEFAULT 0, Falha_SL4_RH INTEGER DEFAULT 0, Falha_SL4_Luz INTEGER DEFAULT 0,
            Falha_SL5_T     INTEGER DEFAULT 0, Falha_SL5_RH INTEGER DEFAULT 0, Falha_SL5_Luz INTEGER DEFAULT 0,
            Falha_SL6_T     INTEGER DEFAULT 0, Falha_SL6_RH INTEGER DEFAULT 0, Falha_SL6_Luz INTEGER DEFAULT 0,
            Falha_SL7_T     INTEGER DEFAULT 0, Falha_SL7_RH INTEGER DEFAULT 0, Falha_SL7_Luz INTEGER DEFAULT 0,
            Falha_SL8_T     INTEGER DEFAULT 0, Falha_SL8_RH INTEGER DEFAULT 0, Falha_SL8_Luz INTEGER DEFAULT 0,
            raw_bloco       TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS alarmes_enviados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local TEXT NOT NULL,
            alarme_detalhe TEXT NOT NULL,
            timestamp TEXT,
            data_captura TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(local, alarme_detalhe)
        )
    ''')
    conn.commit()
    conn.close()

    init_raw_table()

def init_usuarios():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'cliente',
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM usuarios WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hash_senha = pwd_context.hash("bioterio")  
        c.execute("INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, ?)",
                  ("admin", hash_senha, "admin"))
        conn.commit()
    conn.close()


def salvar(dados: dict, raw_bloco: str = ""):
    if not dados:
        return
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    falhas = dados.get("Falhas_SL", {})
    
    row = {
        'data_captura': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Timestamp': dados.get("Timestamp", ""),
        'Local': dados.get("Local", ""),
        'Sensor_ID': dados.get("Sensor_ID", ""),
        'Sinal': dados.get("Sinal", ""),
        'VBAT': dados.get("VBAT", ""),
        'Energia': dados.get("Energia", ""),
        'SL1_T': dados.get("SL1_T", ""), 'SL1_RH': dados.get("SL1_RH", ""), 'SL1_Luz': dados.get("SL1_Luz", ""),
        'SL2_T': dados.get("SL2_T", ""), 'SL2_RH': dados.get("SL2_RH", ""), 'SL2_Luz': dados.get("SL2_Luz", ""),
        'SL3_T': dados.get("SL3_T", ""), 'SL3_RH': dados.get("SL3_RH", ""), 'SL3_Luz': dados.get("SL3_Luz", ""),
        'SL4_T': dados.get("SL4_T", ""), 'SL4_RH': dados.get("SL4_RH", ""), 'SL4_Luz': dados.get("SL4_Luz", ""),
        'SL5_T': dados.get("SL5_T", ""), 'SL5_RH': dados.get("SL5_RH", ""), 'SL5_Luz': dados.get("SL5_Luz", ""),
        'SL6_T': dados.get("SL6_T", ""), 'SL6_RH': dados.get("SL6_RH", ""), 'SL6_Luz': dados.get("SL6_Luz", ""),
        'SL7_T': dados.get("SL7_T", ""), 'SL7_RH': dados.get("SL7_RH", ""), 'SL7_Luz': dados.get("SL7_Luz", ""),
        'SL8_T': dados.get("SL8_T", ""), 'SL8_RH': dados.get("SL8_RH", ""), 'SL8_Luz': dados.get("SL8_Luz", ""),
        'Falha_SL1_T': 1 if falhas.get("SL1_T") else 0,
        'Falha_SL1_RH': 1 if falhas.get("SL1_RH") else 0,
        'Falha_SL1_Luz': 1 if falhas.get("SL1_Luz") else 0,
        'Falha_SL2_T': 1 if falhas.get("SL2_T") else 0,
        'Falha_SL2_RH': 1 if falhas.get("SL2_RH") else 0,
        'Falha_SL2_Luz': 1 if falhas.get("SL2_Luz") else 0,
        'Falha_SL3_T': 1 if falhas.get("SL3_T") else 0,
        'Falha_SL3_RH': 1 if falhas.get("SL3_RH") else 0,
        'Falha_SL3_Luz': 1 if falhas.get("SL3_Luz") else 0,
        'Falha_SL4_T': 1 if falhas.get("SL4_T") else 0,
        'Falha_SL4_RH': 1 if falhas.get("SL4_RH") else 0,
        'Falha_SL4_Luz': 1 if falhas.get("SL4_Luz") else 0,
        'Falha_SL5_T': 1 if falhas.get("SL5_T") else 0,
        'Falha_SL5_RH': 1 if falhas.get("SL5_RH") else 0,
        'Falha_SL5_Luz': 1 if falhas.get("SL5_Luz") else 0,
        'Falha_SL6_T': 1 if falhas.get("SL6_T") else 0,
        'Falha_SL6_RH': 1 if falhas.get("SL6_RH") else 0,
        'Falha_SL6_Luz': 1 if falhas.get("SL6_Luz") else 0,
        'Falha_SL7_T': 1 if falhas.get("SL7_T") else 0,
        'Falha_SL7_RH': 1 if falhas.get("SL7_RH") else 0,
        'Falha_SL7_Luz': 1 if falhas.get("SL7_Luz") else 0,
        'Falha_SL8_T': 1 if falhas.get("SL8_T") else 0,
        'Falha_SL8_RH': 1 if falhas.get("SL8_RH") else 0,
        'Falha_SL8_Luz': 1 if falhas.get("SL8_Luz") else 0,
        'raw_bloco': raw_bloco
    }
    
    columns = ', '.join(row.keys())
    placeholders = ', '.join(['?'] * len(row))
    query = f"INSERT INTO leituras ({columns}) VALUES ({placeholders})"
    
    c.execute(query, list(row.values()))
    conn.commit()
    conn.close()

def atualizar_ultimo_alarme(local: str, detalhe: str, timestamp: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO ultimo_alarme (local, alarme_detalhe, timestamp, data_captura)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (local, detalhe, timestamp))
    conn.commit()
    conn.close()

def get_ultimo_alarme(local: str) -> tuple:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT alarme_detalhe, timestamp FROM ultimo_alarme WHERE local = ?", (local,))
    row = c.fetchone()
    conn.close()
    return row if row else (None, None)

def get_phones_for_local(local: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT phones FROM usuarios WHERE bioterios LIKE ? AND ativo = 1", (f"%{local}%",))
    results = c.fetchall()
    conn.close()
    
    phones = []
    for row in results:
        if row[0]:
            phones.extend([p.strip() for p in row[0].split(',') if p.strip()])
    return phones

def get_bioterios_for_user(username: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT bioterios FROM usuarios WHERE username = ? AND ativo = 1", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return [b.strip() for b in row[0].split(',') if b.strip()]
    return []

def ja_processado(timestamp, sensor_id, local):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM leituras WHERE Timestamp = ? AND Sensor_ID = ? AND Local = ?", (timestamp, sensor_id, local))
    existe = c.fetchone()[0] > 0
    conn.close()
    return existe

def registrar_alarme_enviado(local: str, detalhe: str, timestamp: str):
    if not detalhe or not local:
        return
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO alarmes_enviados (local, alarme_detalhe, timestamp)
        VALUES (?, ?, ?)
    ''', (local, detalhe, timestamp))
    conn.commit()
    conn.close()


def ja_enviado_alarme(local: str, detalhe: str) -> bool:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM alarmes_enviados WHERE local = ? AND alarme_detalhe = ?", (local, detalhe))
    existe = c.fetchone()[0] > 0
    conn.close()
    return existe


def init_raw_table():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS raw (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            recebido_em     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            conteudo        TEXT UNIQUE NOT NULL,
            processado      INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()


def registrar_raw_bloco(bloco: str) -> bool:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    try:
        c.execute(
            "INSERT INTO raw (conteudo) VALUES (?)",
            (bloco.strip(),)
        )
        conn.commit()
        conn.close()
        return True   
    except sqlite3.IntegrityError:
        conn.close()
        return False
    except Exception as e:
        print(f"Erro ao registrar raw: {e}")
        conn.close()
        return False
