from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import mysql.connector
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from bolas_locas.webhook import router as webhook_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",  # Para Live Server de VS Code
        "http://127.0.0.1:80",  # Si corres FastAPI localmente
        "https://www.solutions-systems.com",  # Tu dominio en producción
    ],  # Asegúrate de que este es el dominio correcto
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos los métodos HTTP
    allow_headers=["*"],  # Permitir todos los headers
)


app.include_router(webhook_router)

# ✅ Función para conectar a la base de datos
def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
