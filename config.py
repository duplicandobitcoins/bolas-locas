import os

# Configuración de la base de datos
DB_HOST = os.getenv("MYSQLHOST", "mysql.railway.internal")
DB_PORT = int(os.getenv("MYSQLPORT", 3306))
DB_USER = os.getenv("MYSQLUSER", "root")
DB_PASSWORD = os.getenv("MYSQLPASSWORD", "gipLtWlfZfkaopbYuWSfKmbnxxwQuhLZ")
DB_NAME = os.getenv("MYSQLDATABASE", "railway")

# Diccionario para conexiones
db_config = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME
}
