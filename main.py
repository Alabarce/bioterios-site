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
from database import init_db, init_usuarios, salvar, get_bioterios_for_user
from parser import parse_dados
import threading
from scraper import rodar_scraper

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_WHATSAPP_NUMBER")

TWILIO_CLIENT = Client(account_sid, auth_token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_usuarios()
    scraper_thread = threading.Thread(target=rodar_scraper, daemon=True)
    scraper_thread.start()
    print("✅ Scraper iniciado em background")
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
async def dashboard(request: Request, user=Depends(get_current_user)):
    bioterios_permitidos = get_bioterios_for_user(user["username"])
    if user["role"] == "admin" or not bioterios_permitidos:
        bioterios_permitidos = None

    conn = sqlite3.connect("leituras.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    leituras = {
        "ufmg": {"salas": [{} for _ in range(8)], "ultima_leitura": None},
        "lammebio": {"salas": [{} for _ in range(4)], "ultima_leitura": None}
    }

    if bioterios_permitidos:
        placeholders = ','.join('?' for _ in bioterios_permitidos)
        c.execute(f"""
            SELECT * FROM leituras t1
            WHERE data_captura = (
                SELECT MAX(data_captura) 
                FROM leituras t2 
                WHERE t2.Local = t1.Local
            )
            AND Local IN ({placeholders})
        """, bioterios_permitidos)
    else:
        c.execute("""
            SELECT * FROM leituras t1
            WHERE data_captura = (
                SELECT MAX(data_captura) 
                FROM leituras t2 
                WHERE t2.Local = t1.Local
            )
        """)

    rows = c.fetchall()

    for row in rows:
        local = row["Local"].upper()
        ultima = row["Timestamp"] or row["data_captura"] 

        if "UFMG" in local or "CENTRAL" in local:
            leituras["ufmg"]["ultima_leitura"] = ultima
            for i in range(1, 9):
                sala_key = f"SL{i}"
                leituras["ufmg"]["salas"][i-1] = {
                    "numero": i,
                    "temperatura": row[f"{sala_key}_T"] or "---",
                    "umidade": row[f"{sala_key}_RH"] or "---",
                    "luz": row[f"{sala_key}_Luz"] or "---",
                    "falha_t": row[f"Falha_{sala_key}_T"] or 0,
                    "falha_rh": row[f"Falha_{sala_key}_RH"] or 0,
                    "falha_luz": row[f"Falha_{sala_key}_Luz"] or 0,
                    "ultima_atualizacao": ultima
                }
        elif "LAMMEBIO" in local:
            leituras["lammebio"]["ultima_leitura"] = ultima
            for i in range(1, 5):
                sala_key = f"SL{i}"
                leituras["lammebio"]["salas"][i-1] = {
                    "numero": i,
                    "temperatura": row[f"{sala_key}_T"] or "---",
                    "umidade": row[f"{sala_key}_RH"] or "---",
                    "luz": row[f"{sala_key}_Luz"] or "---",
                    "falha_t": row[f"Falha_{sala_key}_T"] or 0,
                    "falha_rh": row[f"Falha_{sala_key}_RH"] or 0,
                    "falha_luz": row[f"Falha_{sala_key}_Luz"] or 0,
                    "ultima_atualizacao": ultima
                }

    conn.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "leituras": leituras,
        "user": user
    })

@app.get("/admin/usuarios", response_class=HTMLResponse)
async def admin_usuarios(request: Request, user = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403)
    
    conn = sqlite3.connect("leituras.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, username, role, ativo, telefone, bioterios 
        FROM usuarios 
        ORDER BY username
    """)
    usuarios = c.fetchall()
    conn.close()
    
    return templates.TemplateResponse("admin/usuarios.html", {
        "request": request,
        "usuarios": usuarios,
        "user": user
    })


@app.post("/admin/usuarios/criar")
async def criar_usuario(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("cliente"),
    telefone: str = Form(""),
    bioterios: str = Form(""),
    user = Depends(get_current_user)
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403)
    
    hash_senha = pwd_context.hash(password)
    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO usuarios (username, password_hash, role, telefone, bioterios) VALUES (?, ?, ?, ?, ?)",
            (username, hash_senha, role, telefone.strip(), bioterios.strip())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return templates.TemplateResponse("admin/usuarios.html", {
            "request": request,
            "usuarios": [],
            "user": user,
            "error": "Usuário já existe"
        })
    conn.close()
    return RedirectResponse("/admin/usuarios", status_code=303)


@app.post("/admin/usuarios/atualizar/{user_id}")
async def atualizar_usuario(
    user_id: int,
    telefone: str = Form(default=""),
    bioterios: str = Form(default=""),
    user = Depends(get_current_user)
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403)
    
    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()
    c.execute(
        "UPDATE usuarios SET telefone = ?, bioterios = ? WHERE id = ?",
        (telefone.strip(), bioterios.strip(), user_id)
    )
    conn.commit()
    conn.close()
    
    return RedirectResponse("/admin/usuarios", status_code=303)


@app.get("/export-csv")
async def export_csv(user = Depends(get_current_user)):
    bioterios = get_bioterios_for_user(user["username"])
    if user["role"] == "admin" or not bioterios:
        bioterios = None

    conn = sqlite3.connect("leituras.db")
    c = conn.cursor()

    if bioterios:
        placeholders = ','.join('?' for _ in bioterios)
        query = f"""
            SELECT Timestamp, Local, Sensor_ID, Sinal, VBAT, Energia, Alarme,
                   SL1_T, SL1_RH, SL1_Luz, SL2_T, SL2_RH, SL2_Luz,
                   SL3_T, SL3_RH, SL3_Luz, SL4_T, SL4_RH, SL4_Luz,
                   SL5_T, SL5_RH, SL5_Luz, SL6_T, SL6_RH, SL6_Luz,
                   SL7_T, SL7_RH, SL7_Luz, SL8_T, SL8_RH, SL8_Luz,
                   data_captura
            FROM leituras 
            WHERE Local IN ({placeholders})
            ORDER BY id DESC 
            LIMIT 500
        """
        c.execute(query, bioterios)
    else:
        c.execute("""
            SELECT Timestamp, Local, Sensor_ID, Sinal, VBAT, Energia, Alarme,
                   SL1_T, SL1_RH, SL1_Luz, SL2_T, SL2_RH, SL2_Luz,
                   SL3_T, SL3_RH, SL3_Luz, SL4_T, SL4_RH, SL4_Luz,
                   SL5_T, SL5_RH, SL5_Luz, SL6_T, SL6_RH, SL6_Luz,
                   SL7_T, SL7_RH, SL7_Luz, SL8_T, SL8_RH, SL8_Luz,
                   data_captura
            FROM leituras 
            ORDER BY id DESC 
            LIMIT 500
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
        headers={"Content-Disposition": "attachment; filename=leituras_bioterios.csv"}
    )

@app.get("/historico", response_class=HTMLResponse)
async def historico(request: Request):
    conn = sqlite3.connect("leituras.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT Timestamp, Local, Sensor_ID, Sinal, VBAT, Energia,
               SL1_T, SL1_RH, SL1_Luz, SL2_T, SL2_RH, SL2_Luz,
               SL3_T, SL3_RH, SL3_Luz, SL4_T, SL4_RH, SL4_Luz,
               SL5_T, SL5_RH, SL5_Luz, SL6_T, SL6_RH, SL6_Luz,
               SL7_T, SL7_RH, SL7_Luz, SL8_T, SL8_RH, SL8_Luz,
               Falha_SL1_T, Falha_SL1_RH, Falha_SL1_Luz,
               Falha_SL2_T, Falha_SL2_RH, Falha_SL2_Luz,
               Falha_SL3_T, Falha_SL3_RH, Falha_SL3_Luz,
               Falha_SL4_T, Falha_SL4_RH, Falha_SL4_Luz,
               Falha_SL5_T, Falha_SL5_RH, Falha_SL5_Luz,
               Falha_SL6_T, Falha_SL6_RH, Falha_SL6_Luz,
               Falha_SL7_T, Falha_SL7_RH, Falha_SL7_Luz,
               Falha_SL8_T, Falha_SL8_RH, Falha_SL8_Luz
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

@app.post("/api/receber")
async def receber_bloco(bloco: str = Body(..., media_type="text/plain")):
    dados = parse_dados(bloco)
    if dados is None:
        return {"status": "ignorado"}
    salvar(dados, bloco)
    return {"status": "salvo"}


@app.get("/health")
async def health():
    return {"status": "online"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
