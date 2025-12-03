
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

cfg = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": int(os.getenv("DB_PORT", "3306")),
}

conn = mysql.connector.connect(**cfg)
cur = conn.cursor()
cur.execute("SELECT DATABASE(), USER(), VERSION()")
print(cur.fetchone())
cur.close()
conn.close()

