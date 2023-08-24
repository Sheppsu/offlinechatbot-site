from mysql import connector
from django.conf import settings


def create_db_connection():
    return connector.connect(
        host=settings.BOT_DB_HOST,
        port=settings.BOT_DB_PORT,
        user=settings.BOT_DB_USER,
        password=settings.BOT_DB_PASSWORD,
        database=settings.BOT_DB_DATABASE
    )


def get_database():
    db = settings.BOT_DB or create_db_connection()
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except connector.Error:
        db = create_db_connection()
    return db
