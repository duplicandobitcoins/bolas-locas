from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import mysql.connector
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from bolas_locas.webhook import router as webhook_router

app = FastAPI()

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