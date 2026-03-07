"""
Параметры подключения к PostgreSQL (БД demoex из demoexam_db.sql).
Задай через переменные окружения или измени значения ниже.
"""
import os

DB_CONFIG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": os.environ.get("PGPORT", "5432"),
    "dbname": os.environ.get("PGDATABASE", "demoex"),
    "user": os.environ.get("PGUSER", "postgres"),
    "password": os.environ.get("PGPASSWORD", "1111"),
}
