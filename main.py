from fastapi import FastAPI, Body, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext
import sqlite3
import io
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from twilio.rest import Client
from database import init_db, salvar, get_phones_for_local, get_bioterios_for_user

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_WHATSAPP_NUMBER")

TWILIO_CLIENT = Client(account_sid, auth_token)

ULTIMO_ALERTA = {}

def enviar_alerta_whatsapp(telefone: str, mensagem: str):
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
    alarme_val = dados.get("Alarme", "OK").strip().upper()
    if alarme_val in ["OK", "", None, "FALHA"]:
        return

    local = dados.get("Local", "Desconhecido")
    agora = datetime.now()

    if local in ULTIMO_ALERTA:
        if agora - ULTIMO_ALERTA[local] < timedelta(minutes=10):
            print(f"[ANTISPAM] Alerta ignorado para {local} (menos de 10 min)")
            return

    timestamp = dados.get("Timestamp", agora.strftime("%Y-%m-%d %H:%M:%S"))
    mensagem = f"🚨 ALARME:BIOTERIO_{local}@{alarme_val} detectado em {timestamp} Verifique imediatamente"

    telefones = get_phones_for_local(local)
    enviados = 0
    for tel in telefones:
        if enviar_alerta_whatsapp(tel, mensagem):
            enviados += 1

    if enviados > 0:
        ULTIMO_ALERTA[local] = agora
        print(f"[ALERTA] Enviado para {enviados} cliente(s) → {local}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Monitor Bioterios", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="bioterio-segredo-muito-importante")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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

@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/login")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user = Depends(get_current_user)):
    bioterios = get_bioterios_for_user(user["username"])
    if user["role"] == "admin" or not bioterios:
        bioterios = None  # admin vê todos

    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    
    if bioterios:
        placeholders = ','.join('?' for _ in bioterios)
        query = f"""
            SELECT Local, MAX(data_captura) as ultima, 
                   MAX(Timestamp) as timestamp, Alarme, Energia
            FROM leituras 
            WHERE Local IN ({placeholders})
            GROUP BY Local
            ORDER BY ultima DESC
        """
        c.execute(query, bioterios)
    else:
        c.execute("""
            SELECT Local, MAX(data_captura) as ultima, 
                   MAX(Timestamp) as timestamp, Alarme, Energia
            FROM leituras 
            GROUP BY Local
            ORDER BY ultima DESC
        """)
    
    leituras = c.fetchall()
    conn.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "leituras": leituras,
        "user": user
    })

@app.get("/historico", response_class=HTMLResponse)
async def historico(request: Request, user = Depends(get_current_user)):
    bioterios = get_bioterios_for_user(user["username"])
    if user["role"] == "admin" or not bioterios:
        bioterios = None

    conn = sqlite3.connect("leituras.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if bioterios:
        placeholders = ','.join('?' for _ in bioterios)
        query = f"""
            SELECT * FROM leituras 
            WHERE Local IN ({placeholders})
            ORDER BY id DESC LIMIT 300
        """
        c.execute(query, bioterios)
    else:
        c.execute("SELECT * FROM leituras ORDER BY id DESC LIMIT 300")
    
    rows = c.fetchall()
    headers = [desc[0] for desc in c.description]
    conn.close()

    return templates.TemplateResponse("historico.html", {
        "request": request,
        "headers": headers,
        "rows": rows,
        "user": user
    })

@app.post("/api/receber")
async def receber_bloco(bloco: str = Body(..., media_type="text/plain")):
    from parser import parse_dados  # assumindo que você tem esse módulo
    dados = parse_dados(bloco)
    salvar(dados, bloco)
    notificar_clientes_sobre_alarme(dados)
    return {"status": "salvo"}

@app.get("/admin/usuarios", response_class=HTMLResponse)
async def admin_usuarios(request: Request, user = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403)
    
    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    c.execute("SELECT id, username, role, ativo, phones, bioterios FROM usuarios ORDER BY username")
    usuarios = c.fetchall()
    conn.close()
    
    return templates.TemplateResponse("admin/usuarios.html", {
        "request": request,
        "usuarios": usuarios,
        "user": user
    })

@app.post("/admin/usuarios/atualizar/{user_id}")
async def atualizar_usuario(
    user_id: int,
    phones: str = Form(default=""),
    bioterios: str = Form(default=""),
    user = Depends(get_current_user)
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403)
    
    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    c.execute(
        "UPDATE usuarios SET phones = ?, bioterios = ? WHERE id = ?",
        (phones.strip(), bioterios.strip(), user_id)
    )
    conn.commit()
    conn.close()
    
    return RedirectResponse("/admin/usuarios", status_code=303)

@app.get("/health")
async def health():
    return {"status": "online"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)