from fastapi import FastAPI, Body, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer
import sqlite3
import io
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from twilio.rest import Client
from database import init_db, init_usuarios, salvar
from parser import parse_dados

# ────────────────────────────────────────────────
# Config Twilio + antispam
# ────────────────────────────────────────────────
load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_WHATSAPP_NUMBER")

if not all([account_sid, auth_token, TWILIO_FROM]):
    print("⚠️ Credenciais Twilio incompletas no .env")
    # Opcional: raise ValueError("Credenciais Twilio ausentes") para parar a execução

TWILIO_CLIENT = Client(account_sid, auth_token)
# Antispam simples: último envio por local/medidor
ULTIMO_ALERTA = {}  # chave: Local, valor: datetime do último envio

def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


def enviar_alerta_whatsapp(telefone: str, mensagem: str):
    """Envia mensagem WhatsApp via Twilio"""
    if not telefone.startswith("+"):
        telefone = f"+{telefone}"
    
    try:
        msg = TWILIO_CLIENT.messages.create(
            from_=TWILIO_FROM,
            to=f"whatsapp:{telefone}",
            body=mensagem
        )
        print(f"[TWILIO] Enviado → SID: {msg.sid} | Para: {telefone}")
        return True
    except Exception as e:
        print(f"[TWILIO ERRO] Falha para {telefone}: {str(e)}")
        return False

def notificar_clientes_sobre_alarme(dados: dict):


    print("[DEBUG] Dados recebidos no alerta:", dados)  # mostra todo o dict parseado
    print("[DEBUG] Valor de Alarme:", dados.get("Alarme", "OK"))
    if dados.get("Alarme", "OK").strip().upper() in ["OK", "", None]:
        print("[DEBUG] Alarme ignorado: valor = OK ou vazio")
        return
 
    local = dados.get("Local", "Desconhecido")  # chave para antispam
    agora = datetime.now()

    # Antispam: máximo 1 alerta por local a cada 10 minutos
    ultimo = ULTIMO_ALERTA.get(local)
    if ultimo and agora - ultimo < timedelta(minutes=10):
        print(f"[ANTISPAM] Alerta ignorado para {local} (dentro de 10 min do último)")
        return

    # Monta mensagem
    timestamp = dados.get("Timestamp", agora.strftime("%Y-%m-%d %H:%M:%S"))
    alarme = dados.get("Alarme", "Desconhecido")

    mensagem = (
        f"🚨 ALERTA BIOTÉRIO\n"
        f"Local: {local}\n"
        f"Alarme: {alarme}\n"
        f"Hora: {timestamp}\n"
        f"Verifique o dashboard imediatamente!"
    )

    # Envio fixo só pro seu número (teste atual)
    telefone_teste = "+5561999182112"
    if enviar_alerta_whatsapp(telefone_teste, mensagem):
        print(f"[TESTE] Alerta enviado só para {telefone_teste}")

    # Atualiza o último envio (antispam)
    ULTIMO_ALERTA[local] = agora


# lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_usuarios()
    yield

app = FastAPI(title="Monitor Bioterios", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="bioterio")  

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "bioterio"
serializer = URLSafeTimedSerializer(SECRET_KEY)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ────────────────────────────────────────────────
# Suas rotas existentes (mantidas iguais)
# ────────────────────────────────────────────────

# página admin
@app.get("/admin/usuarios", response_class=HTMLResponse)
async def admin_usuarios(request: Request, user = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    c.execute("SELECT id, username, role, ativo FROM usuarios")
    usuarios = c.fetchall()
    conn.close()
    
    return templates.TemplateResponse("admin/usuarios.html", {
        "request": request,
        "usuarios": usuarios,
        "user": user
    })

@app.post("/admin/usuarios/criar")
async def criar_usuario(request: Request, username: str = Form(...), password: str = Form(...), role: str = Form("cliente"), user = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403)
    
    hash_senha = pwd_context.hash(password)
    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, ?)", (username, hash_senha, role))
        conn.commit()
    except sqlite3.IntegrityError:
        return {"error": "Usuário já existe"}
    conn.close()
    return RedirectResponse(url="/admin/usuarios", status_code=303)

@app.post("/admin/usuarios/excluir/{user_id}")
async def excluir_usuario(user_id: int, user = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403)
    
    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    c.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/usuarios", status_code=303)


# usuário
def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse(url="/")
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    c.execute("SELECT username, password_hash, role FROM usuarios WHERE username = ? AND ativo = 1", (username,))
    user = c.fetchone()
    conn.close()
    
    if not user or not pwd_context.verify(password, user[1]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciais inválidas"})
    
    request.session["user"] = {"username": user[0], "role": user[2]}
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

# logout
@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/login")

# cfg
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# receber dados do scraper
@app.post("/api/receber")
async def receber_bloco(bloco: str = Body(..., media_type="text/plain")):
    dados = parse_dados(bloco)
    salvar(dados, bloco)

    # Dispara o alerta WhatsApp (teste para seu número)
    notificar_clientes_sobre_alarme(dados)

    return {"status": "salvo"}

# dashboard
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user = Depends(get_current_user)):
    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    c.execute("""
        SELECT Timestamp, Local, Alarme, Energia,
               SL1_T, SL1_RH, SL1_Luz, SL2_T, SL2_RH, SL2_Luz,
               SL3_T, SL3_RH, SL3_Luz, SL4_T, SL4_RH, SL4_Luz,
               SL5_T, SL5_RH, SL5_Luz, SL6_T, SL6_RH, SL6_Luz,
               SL7_T, SL7_RH, SL7_Luz, SL8_T, SL8_RH, SL8_Luz,
               data_captura
        FROM leituras ORDER BY id DESC LIMIT 1
    """)
    ultima = c.fetchone()
    conn.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "ultima": ultima
    })

# histórico
@app.get("/historico", response_class=HTMLResponse)
async def historico(request: Request):
    conn = sqlite3.connect("leituras.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT Timestamp, Local, Sensor_ID, Sinal, VBAT, Energia, Alarme,
               SL1_T, SL1_RH, SL1_Luz, SL2_T, SL2_RH, SL2_Luz,
               SL3_T, SL3_RH, SL3_Luz, SL4_T, SL4_RH, SL4_Luz,
               SL5_T, SL5_RH, SL5_Luz, SL6_T, SL6_RH, SL6_Luz,
               SL7_T, SL7_RH, SL7_Luz, SL8_T, SL8_RH, SL8_Luz,
               data_captura
        FROM leituras 
        ORDER BY id DESC 
        LIMIT 150
    """)
    rows = c.fetchall()
    headers = [desc[0] for desc in c.description]
    conn.close()

    return templates.TemplateResponse("historico.html", {
        "request": request,
        "headers": headers,
        "rows": rows
    })

# health
@app.get("/health")
async def health():
    return {"status": "online"}

# exportar CSV
@app.get("/export-csv")
async def export_csv():
    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    c.execute("""
        SELECT Timestamp, Local, Sensor_ID, Sinal, VBAT, Energia, Alarme,
               SL1_T, SL1_RH, SL1_Luz, SL2_T, SL2_RH, SL2_Luz,
               SL3_T, SL3_RH, SL3_Luz, SL4_T, SL4_RH, SL4_Luz,
               SL5_T, SL5_RH, SL5_Luz, SL6_T, SL6_RH, SL6_Luz,
               SL7_T, SL7_RH, SL7_Luz, SL8_T, SL8_RH, SL8_Luz,
               data_captura
        FROM leituras 
        ORDER BY id DESC 
        LIMIT 150
    """)
    rows = c.fetchall()
    headers = [desc[0] for desc in c.description]
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)  
    writer.writerows(rows)    

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=historico_leituras.csv"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)