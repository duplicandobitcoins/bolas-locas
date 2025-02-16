from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import mysql.connector
import re  # Para validaciones
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from decimal import Decimal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os  # Importa el módulo os
import requests  

app = FastAPI()

# Configuración de CORS
origins = [
    "https://www.solutions-systems.com",  # Dominio permitido
    "http://localhost:3000",             # Para desarrollo local
    "http://localhost:5500",  # Para Live Server de VS Code
    "http://127.0.0.1:80",  # Si corres FastAPI localmente
    "http://127.0.0.1:8000",  # Si corres FastAPI localmente
    "http://127.0.0.1",  # Si corres FastAPI localmente
        
        
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,               # Orígenes permitidos
    allow_credentials=True,              # Permitir cookies/credenciales
    allow_methods=["*"],                 # Métodos HTTP permitidos
    allow_headers=["*"],                 # Encabezados permitidos
)

# Obtener la ruta absoluta de la carpeta static
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "bolas_locas", "static")

# Depuración: Imprime los archivos y carpetas en el directorio actual
print("Archivos en el directorio actual:", os.listdir("."))
print("Archivos en bolas_locas:", os.listdir("bolas_locas"))

'''
# Montar la carpeta /static para servir archivos estáticos
try:
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
except RuntimeError as e:
    print("Error al montar la carpeta static:", e)
'''

router = APIRouter()

# ✅ Función para conectar a la base de datos
def get_db_connection():
   
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
  


# ✅ Función para verificar si un usuario ya está registrado
def check_user_registered(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT numero_celular FROM jugadores WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result  # Retorna None si el usuario no está registrado

# ✅ Función para registrar un usuario
def handle_registrar_usuario(user_id, data):
    print("📝 Acción detectada: Registro de Usuario")

    # ✅ Verificar si el usuario ya está registrado
    usuario = check_user_registered(user_id)
    if usuario:
        return JSONResponse(content={"fulfillmentText": "⚠️ Esta cuenta de Telegram ya está registrada en el Juego Bolas Locas."})

    # ✅ Extraer los parámetros enviados desde Dialogflow
    rtaCelularNequi = data["queryResult"]["parameters"].get("rtaCelularNequi", "").strip()
    rtaAlias = data["queryResult"]["parameters"].get("rtaAlias", "").strip()
    rtaSponsor = data["queryResult"]["parameters"].get("rtaSponsor", "").strip()

    print(f"📌 Datos recibidos - Celular: {rtaCelularNequi}, Alias: {rtaAlias}, Sponsor: {rtaSponsor}")

    # ✅ Validación de parámetros obligatorios
    if not rtaCelularNequi or not rtaAlias or not rtaSponsor:
        return JSONResponse(content={"fulfillmentText": "❌ Faltan parámetros obligatorios. Verifica la información ingresada."})

    # ✅ Validación del número de celular de Nequi
    rtaCelularNequi = re.sub(r"\D", "", rtaCelularNequi)  # Eliminar caracteres no numéricos
    if not re.fullmatch(r"3\d{9}", rtaCelularNequi):
        return JSONResponse(content={"fulfillmentText": "❌ El número de celular debe tener 10 dígitos y empezar por 3."})

    # ✅ Verificar si se debe autoasignar el sponsor
    if rtaSponsor.lower() == "auto":
        rtaSponsor = get_last_registered_alias()
        if not rtaSponsor:
            return JSONResponse(content={"fulfillmentText": "❌ No hay usuarios registrados para asignar como sponsor."})
    else:
        # Verificar si el sponsor existe en la base de datos
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM jugadores WHERE alias = %s", (rtaSponsor,))
        sponsor_exists = cursor.fetchone()
        cursor.close()
        conn.close()

        if not sponsor_exists:
            return JSONResponse(content={"fulfillmentText": f"❌ El usuario {rtaSponsor} no existe. Verifica y vuelve a intentarlo."})

    # ✅ Registrar al usuario en la base de datos
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "INSERT INTO jugadores (numero_celular, alias, sponsor, user_id) VALUES (%s, %s, %s, %s)",
            (rtaCelularNequi, rtaAlias, rtaSponsor, user_id)
        )
        conn.commit()
        print(f"✅ Usuario {rtaAlias} registrado correctamente con sponsor {rtaSponsor}.")
    except Exception as e:
        print(f"❌ Error al registrar el usuario: {e}")
        return JSONResponse(content={"fulfillmentText": "❌ Hubo un error al registrar el usuario."})
    finally:
        cursor.close()
        conn.close()

    return JSONResponse(content={"fulfillmentText": f"✅ Usuario {rtaAlias} registrado correctamente con sponsor {rtaSponsor}."})


# ✅ Función para obtener tableros disponibles
def get_open_tableros():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_tablero, nombre, precio_por_bolita FROM tableros WHERE estado = 'abierto'")
    tableros = cursor.fetchall()

  # Convertir Decimal a float en los valores necesarios
    for tablero in tableros:
        if isinstance(tablero["precio_por_bolita"], Decimal):
            tablero["precio_por_bolita"] = float(tablero["precio_por_bolita"])
   
    cursor.close()
    conn.close()
    return tableros

# ✅ Función para obtener el último usuario registrado
def get_last_registered_alias():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT alias FROM jugadores ORDER BY numero_celular DESC LIMIT 1")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result["alias"] if result else None



# ✅ Función para manejar la selección de "Jugar"
def handle_jugar(user_id):
    print("🎮 Acción detectada: Jugar")

    # Verificar si el usuario está registrado
    usuario = check_user_registered(user_id)
    if not usuario:
        return JSONResponse(content={"fulfillmentText": "❌ No estás registrado en el sistema."})

    # Obtener tableros abiertos
    tableros = get_open_tableros()
    if not tableros:
        return JSONResponse(content={"fulfillmentText": "🚧 No hay tableros disponibles en este momento."})

    mensaje = "🎲 *Selecciona un tablero para jugar:*"
    botones = {"inline_keyboard": []}
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    for tablero in tableros:
        ID_tablero_jackpot= tablero['id_tablero']
        
        print(f"entre al ciclo y el id_tablero es: {ID_tablero_jackpot}")
        
        cursor.execute("SELECT premio_ganador FROM jackpots WHERE id_tablero = %s", (ID_tablero_jackpot,))
        jack_premio = cursor.fetchone()
        
        acumulado = jack_premio['premio_ganador'] if jack_premio else 0
        
        print(f"el premio es: {acumulado}")

        acumulado_currency = "${:,.0f}".format(acumulado).replace(',', '.')
        
        precio_bolita = "${:,.0f}".format(tablero['precio_por_bolita']).replace(',', '.')
        botones["inline_keyboard"].append([
            {"text": f"#ID: {tablero['id_tablero']} - 🟢 {precio_bolita}  - 💰 Acum: {acumulado_currency}", "callback_data": f"t4bl3r0s3l|{tablero['id_tablero']}"}
        ])

    cursor.close()
    conn.close()

    return JSONResponse(content={
        "fulfillmentMessages": [
            {
                "platform": "TELEGRAM",
                "payload": {
                    "telegram": {
                        "parse_mode": "Markdown",
                        "text": mensaje,
                        "reply_markup": botones
                    }
                }
            }
        ]
    })

#########

async def handle_seleccionar_tablero(user_id, rtaTableroID):
    if not rtaTableroID:
        return JSONResponse(content={"fulfillmentText": "❌ No se recibió el ID del tablero."})
    
    id_tablero = rtaTableroID.replace("|","")
    print(f"📝 Acción detectada: Tablero Seleccionado {id_tablero}")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tableros WHERE id_tablero = %s", (id_tablero,))
    tablero = cursor.fetchone()
    
    if not tablero:
        return JSONResponse(content={"fulfillmentText": "❌ Tablero no encontrado."})
    
    cursor.execute("SELECT COUNT(DISTINCT user_id) as inscritos, SUM(cantidad_bolitas) as bolitas_compradas FROM jugadores_tableros WHERE id_tablero = %s", (id_tablero,))
    stats = cursor.fetchone()
    cursor.execute("SELECT * FROM jackpots WHERE id_tablero = %s", (id_tablero,))
    jackpots = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    disponibles = tablero["max_bolitas"] - (stats["bolitas_compradas"] or 0)
    precio_bolita = "${:,.0f}".format(tablero['precio_por_bolita']).replace(',', '.')

    premio_ganador = jackpots['premio_ganador'] if jackpots else 0

    jackpot = "${:,.0f}".format(premio_ganador).replace(',', '.')
    
    return JSONResponse(content={
        "fulfillmentMessages": [{
            "payload": {
                "telegram": {
                    "text": f"📋 Tablero ID: {tablero['id_tablero']}\n\n🟢 Precio/Bolita: {precio_bolita}\n🔹 Mín. por jugador: {tablero['min_bolitas_por_jugador']}\n🔷 Máx. por jugador: {tablero['max_bolitas_por_jugador']}\n🙂 Jugadores inscritos: {stats['inscritos']}\n\n💰 ACUMULADO: {jackpot}",
                    "reply_markup": {"inline_keyboard": [[{"text": "👉 Comprar Bolitas 🚀", "callback_data": f"C0mpr4rB0l1t4s|{id_tablero}"}]]}
                }
            }
        }]
    })

async def handle_comprar_bolitas(user_id, rtaTableroID, rtaCantBolitas):
    if not rtaTableroID:
        return JSONResponse(content={"fulfillmentText": "❌ No se recibió el ID del tablero."})
    
    id_tablero = rtaTableroID.replace("|","")
    cantidad = rtaCantBolitas
    print(f"📝 Acción detectada: Comora {cantidad} en el tablero {id_tablero}")
    
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT saldo FROM jugadores WHERE user_id = %s", (user_id,))
    jugador = cursor.fetchone()
    
    cursor.execute("SELECT * FROM tableros WHERE id_tablero = %s", (id_tablero,))
    tablero = cursor.fetchone()
    
    cursor.execute("SELECT SUM(cantidad_bolitas) as compradas FROM jugadores_tableros WHERE id_tablero = %s", (id_tablero,))
    stats = cursor.fetchone()

    # 🔹 NUEVO: Obtener la cantidad de bolitas compradas por el jugador en este tablero
    cursor.execute("SELECT SUM(cantidad_bolitas) AS compradas_por_jugador FROM jugadores_tableros WHERE user_id = %s AND id_tablero = %s", (user_id, id_tablero))
    jugador_stats = cursor.fetchone()

     # 🔹 NUEVO: Obtener el monto actual del jackpot del tablero
    cursor.execute("SELECT monto_acumulado FROM jackpots WHERE id_tablero = %s", (id_tablero,))
    jackpot = cursor.fetchone()

    cursor.execute("SELECT * FROM configuracion_pagos WHERE id_config = %s", (1,))
    porcentaje_pagos = cursor.fetchone()
    
    
    cursor.close()
    conn.close()
    
    costo_total = int(cantidad) * tablero["precio_por_bolita"]
    ## disponibles = tablero["max_bolitas"] - (stats["compradas"] or 0)
    bolitas_compradas_jugador = jugador_stats["compradas_por_jugador"] or 0
    bolitas_totales_despues_compra = bolitas_compradas_jugador + int(cantidad)
    monto_casa = (jackpot['monto_acumulado'] + costo_total) * porcentaje_pagos["porcentaje_casa"] if jackpot else (costo_total * porcentaje_pagos["porcentaje_casa"])
    monto_sponsor = (jackpot['monto_acumulado'] + costo_total) * porcentaje_pagos["porcentaje_sponsor"] if jackpot else  (costo_total * porcentaje_pagos["porcentaje_sponsor"])
    monto_ganador = (jackpot['monto_acumulado'] + costo_total) * porcentaje_pagos["porcentaje_ganador"] if jackpot else (costo_total * porcentaje_pagos["porcentaje_ganador"])
    

    
    if jugador["saldo"] < costo_total:
        return JSONResponse(content={"fulfillmentText": "❌ No tienes saldo suficiente."})
    if cantidad < tablero["min_bolitas_por_jugador"] or cantidad > tablero["max_bolitas_por_jugador"]:
        return JSONResponse(content={"fulfillmentText": "❌ Cantidad de bolitas fuera del rango permitido."})
    '''if cantidad > disponibles:
        return JSONResponse(content={"fulfillmentText": "❌ No hay suficientes bolitas disponibles."})'''
    if bolitas_totales_despues_compra > tablero["max_bolitas_por_jugador"]:
        return JSONResponse(content={"fulfillmentText": f"❌ No puedes comprar más bolitas. Ya tienes {bolitas_compradas_jugador} y el límite es {tablero['max_bolitas_por_jugador']}."})

    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE jugadores SET saldo = saldo - %s WHERE user_id = %s", (costo_total, user_id))
    cursor.execute("INSERT INTO jugadores_tableros (user_id, id_tablero, cantidad_bolitas, monto_pagado) VALUES (%s, %s, %s, %s)", (user_id, id_tablero, cantidad, costo_total))
    if jackpot:
        cursor.execute("UPDATE jackpots SET monto_acumulado = monto_acumulado + %s WHERE id_tablero = %s", (costo_total, id_tablero))
        cursor.execute("UPDATE jackpots SET acum_bolitas = acum_bolitas + %s WHERE id_tablero = %s", (cantidad, id_tablero))
        cursor.execute("UPDATE jackpots SET ganancia_bruta =  %s, premio_sponsor = %s, premio_ganador = %s WHERE id_tablero = %s", (monto_casa, monto_sponsor, monto_ganador, id_tablero))
    
    else:
        cursor.execute("INSERT INTO jackpots (id_tablero, acum_bolitas, monto_acumulado, ganancia_bruta, premio_sponsor, premio_ganador) VALUES (%s, %s, %s, %s, %s, %s)", (id_tablero, cantidad, costo_total, monto_casa, monto_sponsor, monto_ganador))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return JSONResponse(content={"fulfillmentText": "✅ Compra realizada con éxito."})

# ✅ Función para manejar "MisTablerosAbiertos"
def handle_mis_tableros_abiertos(user_id):
    print("📌 Acción detectada: MisTablerosAbiertos")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

        
    # ✅ Consulta corregida para cumplir con sql_mode=only_full_group_by
    cursor.execute("""
        SELECT 
            jt.id_tablero,
            MAX(t.fecha_creacion) AS fecha_creacion,  # Usamos MAX para cumplir con only_full_group_by
            SUM(jt.cantidad_bolitas) AS bolitas_compradas_usuario,
            MAX(j.acum_bolitas) AS bolitas_totales_tablero,  # Usamos MAX para cumplir con only_full_group_by
            MAX(j.premio_ganador) AS acumulado_tablero  # Usamos MAX para cumplir con only_full_group_by
        FROM 
            jugadores_tableros jt
        JOIN 
            tableros t ON jt.id_tablero = t.id_tablero
        LEFT JOIN 
            jackpots j ON jt.id_tablero = j.id_tablero
        WHERE 
            jt.user_id = %s AND t.estado = 'abierto'
        GROUP BY 
            jt.id_tablero
    """, (user_id,))
    
    tableros = cursor.fetchall()
    cursor.close()
    conn.close()

    if not tableros:
        return JSONResponse(content={"fulfillmentText": "📭 No estás inscrito en ningún tablero abierto en este momento."})

    # ✅ Construir el mensaje con los tableros
    mensaje = "📋 *Mis Tableros Abiertos:*\n\n"
    for tablero in tableros:
        fecha_creacion = tablero["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
        bolitas_compradas = tablero["bolitas_compradas_usuario"]
        bolitas_totales = tablero["bolitas_totales_tablero"]
        acumulado = "${:,.0f}".format(tablero["acumulado_tablero"]).replace(',', '.')

        mensaje += (
            f"🔹 *ID Tablero:* {tablero['id_tablero']}\n"
            f"📅 *Fecha de creación:* {fecha_creacion}\n"
            f"🔮 *Bolitas compradas por ti:* {bolitas_compradas}\n"
            f"💠 *Bolitas totales en el tablero:* {bolitas_totales}\n"
            f"💰 *Acumulado del tablero:* {acumulado}\n\n"
        )

    return JSONResponse(content={
        "fulfillmentMessages": [
            {
                "platform": "TELEGRAM",
                "payload": {
                    "telegram": {
                        "parse_mode": "Markdown",
                        "text": mensaje
                    }
                }
            }
        ]
    })

######### 🟡🟡🟡 Fin Funcion Tableros Abiertos

# ✅ Función para manejar "MisTablerosJugados"
def handle_mis_tableros_jugados(user_id, rtaMes, rtaAnio):
    print("📌 Acción detectada: MisTablerosJugados")

    # Validar que los parámetros de mes y año estén presentes
    if not rtaMes or not rtaAnio:
        return JSONResponse(content={"fulfillmentText": "❌ Faltan parámetros obligatorios (mes o año)."})

    # Convertir el mes y año a enteros
    try:
        mes = int(rtaMes)
        anio = int(rtaAnio)
    except ValueError:
        return JSONResponse(content={"fulfillmentText": "❌ El mes y el año deben ser números válidos."})

    # Validar que el mes esté en el rango correcto (1-12)
    if mes < 1 or mes > 12:
        return JSONResponse(content={"fulfillmentText": "❌ El mes debe estar entre 1 y 12."})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Obtener los tableros en los que el usuario ha participado en el mes y año especificados
    cursor.execute("""
        SELECT DISTINCT 
            jt.id_tablero
        FROM 
            jugadores_tableros jt
        JOIN 
            tableros t ON jt.id_tablero = t.id_tablero
        WHERE 
            jt.user_id = %s
            AND YEAR(t.fecha_creacion) = %s
            AND MONTH(t.fecha_creacion) = %s
            AND t.estado != 'abierto'
    """, (user_id, anio, mes))

    tableros = cursor.fetchall()
    cursor.close()
    conn.close()

    if not tableros:
        return JSONResponse(content={"fulfillmentText": f"📭 No participaste en ningún tablero en {mes}/{anio}."})

    # ✅ Construir la lista de IDs de tableros separados por comas
    lista_tableros = ", ".join(str(tablero["id_tablero"]) for tablero in tableros)

    return JSONResponse(content={
        "fulfillmentText": f"📋 ID de los Tableros en los que participaste en {mes}/{anio}:\n\n {lista_tableros}"
    })

##### 🟡🟡🟡 Fin Función Mis Tableros Jugados

# ✅ Función para manejar "ConsultarTablero"
def handle_consulta_tablero(rtaIDTablero):
    print("📌 Acción detectada: ConsultarTablero")

    # Validar que el parámetro rtaIDTablero esté presente
    if not rtaIDTablero:
        return JSONResponse(content={"fulfillmentText": "❌ Faltan parámetros obligatorios (ID del tablero)."})

    # Convertir el ID del tablero a entero
    try:
        id_tablero = int(rtaIDTablero)
    except ValueError:
        return JSONResponse(content={"fulfillmentText": "❌ El ID del tablero debe ser un número válido."})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Obtener los datos de la tabla jackpots para el ID de tablero especificado
    cursor.execute("""
        SELECT 
            id_tablero,
            monto_acumulado,
            alias_ganador,
            sponsor_ganador,
            premio_ganador,
            premio_sponsor,
            estado,
            link_soporte,
            fecha_pago,
            acum_bolitas
        FROM 
            jackpots
        WHERE 
            id_tablero = %s
    """, (id_tablero,))

    jackpot = cursor.fetchone()
    cursor.close()
    conn.close()

    if not jackpot:
        return JSONResponse(content={"fulfillmentText": f"❌ No se encontró información para el tablero con ID {id_tablero}."})

    # ✅ Construir el mensaje con los datos del jackpot
    mensaje = (
        f"📋 *Información del Tablero ID {jackpot['id_tablero']}:*\n\n"
        f"💰 *Monto Acumulado:* ${jackpot['monto_acumulado']:,.0f}\n"
        f"🔮 *Bolitas Jugadas:* {jackpot['acum_bolitas']}\n"
        f"🏆 *Usuario Ganador:* {jackpot['alias_ganador'] or 'N/A'}\n"
        f"🤝 *Sponsor del Ganador:* {jackpot['sponsor_ganador'] or 'N/A'}\n"
        f"🎁 *Premio del Ganador:* ${jackpot['premio_ganador']:,.0f}\n"
        f"🎁 *Premio del Sponsor:* ${jackpot['premio_sponsor']:,.0f}\n\n"
        f"📊 *Estado del tablero:* {jackpot['estado'].capitalize()}\n"
        f"🔗 *Link Soporte pago:* {jackpot['link_soporte'] or 'N/A'}\n"
        f"📅 *Fecha de Pago:* {jackpot['fecha_pago'].strftime('%Y-%m-%d %H:%M:%S') if jackpot['fecha_pago'] else 'N/A'}\n"
        
    )

    return JSONResponse(content={
        "fulfillmentMessages": [
            {
                "platform": "TELEGRAM",
                "payload": {
                    "telegram": {
                        "parse_mode": "Markdown",
                        "text": mensaje
                    }
                }
            }
        ]
    })

##### 🟡🟡🟡 Fin Función Consultar Tablero

# ✅ Función para manejar "MisTablerosGanados"
def handle_mis_tableros_ganados(user_id):
    print("📌 Acción detectada: MisTablerosGanados")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Obtener el alias del usuario
    cursor.execute("SELECT alias FROM jugadores WHERE user_id = %s", (user_id,))
    usuario = cursor.fetchone()

    if not usuario:
        return JSONResponse(content={"fulfillmentText": "❌ No estás registrado en el sistema."})

    alias_usuario = usuario["alias"]

    # ✅ Obtener los tableros en los que el usuario aparece como ganador o sponsor
    cursor.execute("""
        SELECT 
            id_tablero,
            monto_acumulado,
            alias_ganador,
            sponsor_ganador,
            premio_ganador,
            premio_sponsor,
            estado,
            link_soporte,
            fecha_pago,
            acum_bolitas
        FROM 
            jackpots
        WHERE 
            alias_ganador = %s OR sponsor_ganador = %s
    """, (alias_usuario, alias_usuario))

    tableros = cursor.fetchall()
    cursor.close()
    conn.close()

    if not tableros:
        return JSONResponse(content={"fulfillmentText": "📭 No has ganado ni has sido sponsor en ningún tablero ganador."})

    # ✅ Construir el mensaje con los tableros
    mensaje = "🏆 *Tus Tableros Ganados o con ganacias como Sponsor:*\n\n"
    for tablero in tableros:
        mensaje += (
            f"🔹 *ID Tablero:* {tablero['id_tablero']}\n"
            f"💰 *Monto Acumulado:* ${tablero['monto_acumulado']:,.0f}\n"
            f"🔮 *Bolitas Acumuladas:* {tablero['acum_bolitas']}\n"
            f"🏆 *Alias del Ganador:* {tablero['alias_ganador'] or 'N/A'}\n"
            f"🤝 *Sponsor del Ganador:* {tablero['sponsor_ganador'] or 'N/A'}\n"
            f"🎁 *Premio del Ganador:* ${tablero['premio_ganador']:,.0f}\n"
            f"🎁 *Premio del Sponsor:* ${tablero['premio_sponsor']:,.0f}\n"
            f"📊 *Estado:* {tablero['estado'].capitalize()}\n"
            f"🔗 *Link de Soporte:* {tablero['link_soporte'] or 'N/A'}\n"
            f"📅 *Fecha de Pago:* {tablero['fecha_pago'].strftime('%Y-%m-%d %H:%M:%S') if tablero['fecha_pago'] else 'N/A'}\n\n"
            
        )

    return JSONResponse(content={
        "fulfillmentMessages": [
            {
                "platform": "TELEGRAM",
                "payload": {
                    "telegram": {
                        "parse_mode": "Markdown",
                        "text": mensaje
                    }
                }
            }
        ]
    })

##### 🟡🟡🟡 Fin Función Mis Tableros Ganados


# ✅ Webhook de Dialogflow
@router.post("/webhook")
async def handle_dialogflow_webhook(request: Request):
    print("🚨 Webhook llamado") 
    data = await request.json()

    # ✅ Extraer el user_id de Telegram
    user_id = None
    try:
        user_id = data["originalDetectIntentRequest"]["payload"]["data"]["from"]["id"]
    except KeyError:
        try:
            user_id = data["originalDetectIntentRequest"]["payload"]["data"]["callback_query"]["from"]["id"]
            print(f"📌 User ID obtenido desde callback: {user_id}")
        except KeyError:
            return JSONResponse(content={"fulfillmentText": "❌ Error: No se pudo obtener el ID de usuario de Telegram."})

    # ✅ Verificar la acción
    action = data["queryResult"].get("action")

    if action == "actDatosCuenta":
        return handle_mi_cuenta(user_id)

    if action == "actCambiarNequi":
        rtaNuevoNequi = data["queryResult"]["parameters"].get("rtaNuevoNequi")
        return handle_cambiar_nequi(user_id, rtaNuevoNequi)

    if action == "actJugar":
        return handle_jugar(user_id)

    if action == "actRegistrarUsuario":
        return handle_registrar_usuario(user_id, data)

    if action == "actTableroSelect":
        rtaTableroID = data["queryResult"]["parameters"].get("rtaTableroID")
        return await handle_seleccionar_tablero(user_id, rtaTableroID)
    
    if action == "actComprarBolitas":
        rtaCantBolitas = data["queryResult"]["parameters"].get("rtaCantBolitas")
        rtaTableroID = data["queryResult"]["parameters"].get("rtaTableroID")
        return await handle_comprar_bolitas(user_id, rtaTableroID, rtaCantBolitas)

    if action == "actMisTabAbiertos":
        return handle_mis_tableros_abiertos(user_id)

    # ✅ Nuevo action para MisTablerosJugados
    if action == "actMisTabJugados":
        rtaMes = data["queryResult"]["parameters"].get("rtaMes")
        rtaAnio = data["queryResult"]["parameters"].get("rtaAnio")
        return handle_mis_tableros_jugados(user_id, rtaMes, rtaAnio)

    
    # ✅ Nuevo action para ConsultarTablero
    if action == "actConsultaTablero":
        rtaIDTablero = data["queryResult"]["parameters"].get("rtaIDTablero")
        return handle_consulta_tablero(rtaIDTablero)

    
    # ✅ Nuevo action para MisTablerosGanados
    if action == "actMisTabGanados":
        return handle_mis_tableros_ganados(user_id)


        # ✅ Nueva acción para Comprar Álbum
    if action == "actComprarAlbum":
        return handle_comprar_album()


    if action == "actComprarAlbumMiniApp":
        return handle_comprar_album_miniapp(user_id)

    return JSONResponse(content={"fulfillmentText": "⚠️ Acción no reconocida."})

# ✅ Función para manejar "MiCuenta"
def handle_mi_cuenta(user_id):
    print("📌 Acción detectada: MiCuenta")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT numero_celular, alias, sponsor, saldo FROM jugadores WHERE user_id = %s", (user_id,))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()

    if not usuario:
        return JSONResponse(content={"fulfillmentText": "❌ No estás registrado en el sistema."})

    saldo_formateado = "${:,.0f}".format(usuario['saldo']).replace(',', '.')
    
    mensaje = (
        f"Tu cuenta en *Bolas Locas:*\n\n"
        f"👤 *Usuario:* _{usuario['alias']}_\n"
        f"📱 *Número registrado en Nequi:* _{usuario['numero_celular']}_\n"
        f"🤝 *Patrocinador:* _{usuario['sponsor']}_\n\n"
        f"💲 *SALDO:* _{saldo_formateado}_\n\n"
        "🔽 ¿Qué quieres hacer?"
    )

    botones = {
        "fulfillmentMessages": [
            {
                "platform": "TELEGRAM",
                "payload": {
                    "telegram": {
                        "parse_mode": "Markdown",
                        "text": mensaje,
                        "reply_markup": {
                            "inline_keyboard": [
                                [{"text": "💲 Recargar saldo", "callback_data": "recargar_saldo"}],
                                [{"text": "🔄 Cambiar número Nequi", "callback_data": "c4mb14r_n3qu1"}],
                                [{"text": "📋 Mis tableros", "callback_data": "M1st4bl4s"}],
                                [{"text": "🔮 Jugar", "callback_data": "1n1c10Ju3g0"}]
                            
                            ]
                        }
                    }
                }
            }
        ]
    }

    return JSONResponse(content=botones)

# ✅ Función para manejar el cambio de número de Nequi
def handle_cambiar_nequi(user_id, rtaNuevoNequi):
    print("🔄 Acción detectada: CambiarNequi")

    # Validaciones del nuevo número de Nequi
    rtaNuevoNequi = re.sub(r"\D", "", str(rtaNuevoNequi))
    if not re.fullmatch(r"3\d{9}", rtaNuevoNequi):
        return JSONResponse(content={"fulfillmentText": "❌ El número de celular debe tener 10 dígitos y empezar por 3."})

    # Actualizar el número en la base de datos
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("UPDATE jugadores SET numero_celular = %s WHERE user_id = %s", (rtaNuevoNequi, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    return JSONResponse(content={"fulfillmentText": "✅ Número de Nequi actualizado correctamente."})

def convertir_a_float(data):
    for item in data:
        for key, value in item.items():
            if isinstance(value, Decimal):
                item[key] = float(value)
    return data

# ✅ Endpoint para obtener los tableros abiertos
@router.get("/tableros_abiertos")
def get_tableros_abiertos():
    print("📢 Solicitando tableros abiertos...")

    try:
        tableros = get_open_tableros()
        print(f"✅ Tableros obtenidos: {tableros}")  # 🔍 Ver qué devuelve la consulta

        if not tableros:
            return JSONResponse(content={"message": "No hay tableros abiertos."}, status_code=404)

        return JSONResponse(content=tableros)

    except Exception as e:
        print(f"❌ Error en el endpoint /tableros_abiertos: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# ✅ Endpoint para obtener jugadores de un tablero específico
@router.get("/tablero/{tablero_id}/jugadores")
def get_jugadores_tablero(tablero_id: int):
    print(f"📢 Solicitando jugadores del tablero {tablero_id}...")
 
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        query = """
            SELECT j.user_id, j.alias, j.sponsor, SUM(jt.cantidad_bolitas) AS total_bolitas
            FROM jugadores_tableros jt
            JOIN jugadores j ON jt.user_id = j.user_id
            WHERE jt.id_tablero = %s
            GROUP BY j.user_id, j.alias, j.sponsor
        """
        
        cursor.execute(query, (tablero_id,))
        jugadores = cursor.fetchall()

       # Convertir valores Decimal a float
        jugadores = convertir_a_float(jugadores)

        if not jugadores:
            return JSONResponse(content={"message": "No hay jugadores en este tablero."}, status_code=404)

        return JSONResponse(content=jugadores)

    except Exception as e:
        print(f"❌ Error en el endpoint /tablero/{tablero_id}/jugadores: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

    finally:
        cursor.close()
        conn.close()

##### 🟡🟡🟡 Fin Endpoint para obtener jugadores de un tablero específico


# ✅ Endpoint para obtener los datos del jackpot de un tablero específico
@router.get("/tablero/{id_tablero}/jackpot")
async def obtener_jackpot_tablero(id_tablero: int):
    """
    Endpoint para obtener los datos del jackpot de un tablero específico.
    """
    try:
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Consultar los datos del jackpot para el tablero seleccionado
        query = """
        SELECT id_tablero, acum_bolitas, premio_ganador, premio_sponsor
        FROM jackpots
        WHERE id_tablero = %s
        """
        cursor.execute(query, (id_tablero,))
        jackpot_data = cursor.fetchone()

        # Cerrar la conexión
        cursor.close()
        conn.close()

        if not jackpot_data:
            raise HTTPException(status_code=404, detail="No se encontraron datos del jackpot para este tablero.")

        # Devolver los datos del jackpot
        return {
            
            "id_tablero": jackpot_data["id_tablero"],
            "acum_bolitas": jackpot_data["acum_bolitas"],
            "premio_ganador": jackpot_data["premio_ganador"],
            "premio_sponsor": jackpot_data["premio_sponsor"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener los datos del jackpot: {str(e)}")

##### 🟡🟡🟡 Fin Endpoint para obtener los datos del jackpot de un tablero específico.

from random import randint

@router.post("/simular_compras")
async def simular_compras():
    print("📢 Simulando compras masivas en el tablero ID 4...")
    try:
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Paso 0: Actualizar el saldo de todos los jugadores a 500,000
        print("💰 Actualizando saldo de todos los jugadores a 500,000...")
        cursor.execute("UPDATE jugadores SET saldo = 500000")
        conn.commit()  # Confirmar la actualización
        
        # Paso 1: Truncar la tabla jugadores_tableros
        print("🧹 Truncando la tabla jugadores_tableros...")
        #cursor.execute("TRUNCATE TABLE jugadores_tableros")
        cursor.execute("DELETE from jugadores_tableros WHERE id_tablero = %s", (4,))
        
        # Paso 2: Reiniciar los valores del jackpot para el id_tablero 4
        print("🔄 Reiniciando valores del jackpot para el tablero ID 4...")
        cursor.execute(
            """
            UPDATE jackpots 
            SET 
                monto_acumulado = 0, 
                premio_ganador = 0, 
                premio_sponsor = 0, 
                ganancia_bruta = 0, 
                acum_bolitas = 0
            WHERE id_tablero = %s
            """,
            (4,)
        )
        
        # Confirmar los cambios realizados hasta ahora
        conn.commit()
        
        # Paso 3: Obtener todos los jugadores registrados
        cursor.execute("SELECT user_id, saldo FROM jugadores")
        jugadores = cursor.fetchall()
        
        # Definir el ID del tablero
        id_tablero = 4
        
        # Iterar sobre cada jugador y simular la compra de bolitas
        for jugador in jugadores:
            user_id = jugador["user_id"]
            saldo_actual = jugador["saldo"]
            
            # Consultar los detalles del tablero
            cursor.execute("SELECT * FROM tableros WHERE id_tablero = %s", (id_tablero,))
            tablero = cursor.fetchone()
            if not tablero:
                continue  # Saltar si el tablero no existe
            
            # Generar una cantidad aleatoria de bolitas dentro del rango permitido
            min_bolitas = tablero["min_bolitas_por_jugador"]
            max_bolitas = tablero["max_bolitas_por_jugador"]
            cantidad_bolitas = randint(min_bolitas, max_bolitas)
            
            # Calcular el costo total
            precio_por_bolita = tablero["precio_por_bolita"]
            costo_total = cantidad_bolitas * precio_por_bolita
            
            # Verificar si el jugador tiene suficiente saldo
            if saldo_actual < costo_total:
                print(f"⚠️ Jugador {user_id} no tiene suficiente saldo para comprar {cantidad_bolitas} bolitas.")
                continue
            
            # Verificar si el jugador ya alcanzó el límite máximo de bolitas en el tablero
            cursor.execute(
                "SELECT SUM(cantidad_bolitas) AS compradas_por_jugador FROM jugadores_tableros WHERE user_id = %s AND id_tablero = %s",
                (user_id, id_tablero)
            )
            jugador_stats = cursor.fetchone()
            bolitas_compradas_jugador = jugador_stats["compradas_por_jugador"] or 0
            if bolitas_compradas_jugador + cantidad_bolitas > tablero["max_bolitas_por_jugador"]:
                print(f"⚠️ Jugador {user_id} excede el límite máximo de bolitas en el tablero.")
                continue
            
            # Actualizar el saldo del jugador
            cursor.execute("UPDATE jugadores SET saldo = saldo - %s WHERE user_id = %s", (costo_total, user_id))
            
            # Registrar la compra en la tabla jugadores_tableros
            cursor.execute(
                "INSERT INTO jugadores_tableros (user_id, id_tablero, cantidad_bolitas, monto_pagado) VALUES (%s, %s, %s, %s)",
                (user_id, id_tablero, cantidad_bolitas, costo_total)
            )
            
            # Actualizar el jackpot
            cursor.execute("SELECT * FROM jackpots WHERE id_tablero = %s", (id_tablero,))
            jackpot = cursor.fetchone()
            if jackpot:
                # Calcular los nuevos valores para premio_ganador, premio_sponsor y ganancia_bruta
                nuevo_monto_acumulado = jackpot["monto_acumulado"] + costo_total
                premio_ganador = nuevo_monto_acumulado * Decimal('0.60')  # 60% del monto acumulado
                premio_sponsor = nuevo_monto_acumulado * Decimal('0.06')  # 6% del monto acumulado
                ganancia_bruta = nuevo_monto_acumulado * Decimal('0.34')  # 34% del monto acumulado
                
                # Actualizar el jackpot con los nuevos valores
                cursor.execute(
                    """
                    UPDATE jackpots 
                    SET 
                        monto_acumulado = %s, 
                        acum_bolitas = acum_bolitas + %s,
                        premio_ganador = %s,
                        premio_sponsor = %s,
                        ganancia_bruta = %s
                    WHERE id_tablero = %s
                    """,
                    (
                        nuevo_monto_acumulado,
                        cantidad_bolitas,
                        premio_ganador,
                        premio_sponsor,
                        ganancia_bruta,
                        id_tablero
                    )
                )
            else:
                # Calcular los valores iniciales para premio_ganador, premio_sponsor y ganancia_bruta
                premio_ganador = costo_total * Decimal('0.60')  # 60% del monto acumulado
                premio_sponsor = costo_total * Decimal('0.06')  # 6% del monto acumulado
                ganancia_bruta = costo_total * Decimal('0.34')  # 34% del monto acumulado
                
                # Insertar un nuevo registro en jackpots
                cursor.execute(
                    """
                    INSERT INTO jackpots 
                    (id_tablero, acum_bolitas, monto_acumulado, premio_ganador, premio_sponsor, ganancia_bruta) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        id_tablero,
                        cantidad_bolitas,
                        costo_total,
                        premio_ganador,
                        premio_sponsor,
                        ganancia_bruta
                    )
                )
            
            print(f"✅ Jugador {user_id} compró {cantidad_bolitas} bolitas en el tablero {id_tablero}.")
        
        # Confirmar los cambios en la base de datos
        conn.commit()
        
        # Cerrar la conexión
        cursor.close()
        conn.close()
        return JSONResponse(content={"message": "Simulación de compras completada."})
    
    except Exception as e:
        print(f"❌ Error al simular compras: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

############################################################
##      📚📚📚 Inicio Seccion de ALBUMES 📚📚📚         ##
############################################################

@router.get("/albumes_disponibles")
def get_albumes_disponibles():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id_album, nombre, descripcion, precio FROM albumes WHERE estado = 'activo'")
        albumes = cursor.fetchall()
        # Convertir valores Decimal a float
        albumes = convertir_a_float(albumes)
        cursor.close()
        conn.close()
        if not albumes:
            return JSONResponse(content={"message": "No hay álbumes disponibles."}, status_code=404)
        return JSONResponse(content=albumes)
    except Exception as e:
        print(f"❌ Error en el endpoint /albumes_disponibles: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/iniciar_compra_album")
async def iniciar_compra_album(data: dict):
    user_id = data.get("user_id")
    id_album = data.get("id_album")

    if not user_id or not id_album:
        return JSONResponse(content={"error": "Faltan parámetros obligatorios."}, status_code=400)

    # Verificar si el álbum existe
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM albumes WHERE id_album = %s AND estado = 'activo'", (id_album,))
    album = cursor.fetchone()
    if not album:
        return JSONResponse(content={"error": "El álbum no existe o no está disponible."}, status_code=404)

    # Registrar la compra en estado pendiente
    try:
        cursor.execute(
            "INSERT INTO compras_albumes (user_id, id_album, estado) VALUES (%s, %s, 'pendiente')",
            (user_id, id_album)
        )
        conn.commit()
        id_compra_album = cursor.lastrowid
    except Exception as e:
        conn.rollback()
        return JSONResponse(content={"error": f"Error al registrar la compra: {str(e)}"}, status_code=500)
    finally:
        cursor.close()
        conn.close()

    # Generar solicitud de pago en Bold
    bold_payload = {
        "amount": album["precio"],
        "currency": "COP",
        "description": f"Compra de álbum: {album['nombre']}",
        "callback_url": "https://bolas-locas-production.up.railway.app/callback_bold",
        "reference": str(id_compra_album)  # Usamos el ID de la compra como referencia
    }

    try:
        response = requests.post("https://api.bold.com/payments", json=bold_payload)
        if response.status_code != 200:
            return JSONResponse(content={"error": "Error al generar la solicitud de pago."}, status_code=500)

        payment_url = response.json().get("payment_url")
        return JSONResponse(content={"payment_url": payment_url})
    except Exception as e:
        return JSONResponse(content={"error": f"Error al comunicarse con Bold: {str(e)}"}, status_code=500)
'''
    @router.post("/callback_bold")
async def callback_bold(data: dict):
    reference = data.get("reference")
    status = data.get("status")

    if not reference or not status:
        return JSONResponse(content={"error": "Faltan parámetros obligatorios."}, status_code=400)

    # Actualizar el estado de la compra
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "UPDATE compras_albumes SET estado = %s, fecha_confirmacion = NOW() WHERE id_compra_album = %s",
            (status, reference)
        )
        conn.commit()

        if status == "completado":
            # Asignar las láminas del usuario al álbum
            cursor.execute(
                "INSERT INTO coleccion_laminas (user_id, id_album, id_lamina, cantidad) "
                "SELECT %s, %s, id_lamina, COUNT(*) "
                "FROM laminas_obtenidas "
                "WHERE user_id = %s AND id_lamina IN (SELECT id_lamina FROM laminas WHERE id_album = %s) "
                "GROUP BY id_lamina",
                (user_id, id_album, user_id, id_album)
            )
            conn.commit()
    except Exception as e:
        conn.rollback()
        return JSONResponse(content={"error": f"Error al procesar el callback: {str(e)}"}, status_code=500)
    finally:
        cursor.close()
        conn.close()

    return JSONResponse(content={"message": "Callback procesado correctamente."})
'''
# ✅ Función para manejar la acción de comprar álbum
def handle_comprar_album():
    print("📚 Acción detectada: Comprar Álbum")
    try:
        # Obtener álbumes disponibles directamente desde la función local
        albumes = get_albumes_disponibles_local()

        if not albumes:
            return JSONResponse(content={"fulfillmentText": "📭 No hay álbumes disponibles en este momento."})

        # Construir el mensaje con los álbumes disponibles
        mensaje = "📚 *Álbumes Disponibles:*\n\n"
        botones = {"inline_keyboard": []}

        for album in albumes:
            precio_formateado = "${:,.0f}".format(album["precio"]).replace(',', '.')
            mensaje += f"🔹 *ID:* {album['id_album']} - {album['nombre']}\n"
            mensaje += f"💰 Precio: {precio_formateado}\n\n"
            botones["inline_keyboard"].append([
                {"text": f"🛒 Comprar Álbum {album['id_album']}", "callback_data": f"C0mpr4r4lbum|{album['id_album']}"}
            ])

        return JSONResponse(content={
            "fulfillmentMessages": [
                {
                    "platform": "TELEGRAM",
                    "payload": {
                        "telegram": {
                            "parse_mode": "Markdown",
                            "text": mensaje,
                            "reply_markup": botones
                        }
                    }
                }
            ]
        })
    except Exception as e:
        print(f"❌ Error al procesar la acción actComprarAlbum: {e}")
        return JSONResponse(content={"fulfillmentText": "❌ Hubo un error al procesar la solicitud."})


# ✅ Función local para obtener álbumes disponibles
def get_albumes_disponibles_local():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id_album, nombre, descripcion, precio FROM albumes WHERE estado = 'activo'")
        albumes = cursor.fetchall()

        # Convertir valores Decimal a float
        albumes = convertir_a_float(albumes)

        cursor.close()
        conn.close()

        if not albumes:
            print("⚠️ No se encontraron álbumes disponibles.")
            return []

        print(f"✅ Álbumes obtenidos: {albumes}")  # 🔍 Ver qué devuelve la consulta
        return albumes

    except Exception as e:
        print(f"❌ Error en la función get_albumes_disponibles_local: {e}")
        return []

    
    # ✅ Función para manejar la acción "Comprar Álbum Mini App"
def handle_comprar_album_miniapp(user_id):
    print("🛒 Acción detectada: Comprar Álbum Mini App")

    # URL de la Mini App (asegúrate de que coincida con tu dominio)
    mini_app_url = "http://127.0.0.1/bolas-locas/mini-app"  # Reemplaza con la URL de tu Mini App

    # Construir el mensaje con un botón para abrir la Mini App
    return JSONResponse(content={
        "fulfillmentMessages": [
            {
                "platform": "TELEGRAM",
                "payload": {
                    "telegram": {
                        "text": "🛍️ *Compra un Álbum:*",
                        "reply_markup": {
                            "inline_keyboard": [
                                [{"text": "👉 Abrir Mini App", "web_app": {"url": mini_app_url}}]
                            ]
                        }
                    }
                }
            }
        ]
    })