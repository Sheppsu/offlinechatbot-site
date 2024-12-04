import os
import asyncio
import sys
from datetime import datetime
from psycopg import AsyncConnection
from mysql import connector
from dotenv import load_dotenv

load_dotenv()

import django
os.environ["DJANGO_SETTINGS_MODULE"] = "offlinechatbot.settings"
django.setup()

from main.models import *
from place.models import *


class BotDatabase:
    name = os.getenv("BOT_DB_DATABASE")
    host = os.getenv("BOT_DB_HOST")
    port = int(os.getenv("BOT_DB_PORT"))
    user = os.getenv("BOT_DB_USER")
    password = os.getenv("BOT_DB_PASSWORD")

    def __init__(self):
        self.database = self.create_connection()

    def create_connection(self):
        return connector.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.name
        )

    def ping(self):
        try:
            self.database.ping(reconnect=True, attempts=3, delay=5)
        except connector.Error:
            self.database = self.create_connection()

    def close(self):
        self.database.close()

    def get_cursor(self):
        self.ping()
        return self.database.cursor()


class OldDatabase:
    CONNINFO = "postgresql://postgres:6f1Ca316CB5AdEegD1DfGD4ff1BGCCBE@roundhouse.proxy.rlwy.net:55276/railway"

    def __init__(self, conn: AsyncConnection):
        self._conn: AsyncConnection = conn

    @classmethod
    async def connect(cls) -> "OldDatabase":
        if cls.CONNINFO is None:
            raise RuntimeError("Failed to load the environment variable 'PGURL'")

        return cls(await AsyncConnection.connect(cls.CONNINFO))

    async def close(self) -> None:
        # prevent attempting to use the connection in between now and closing it
        conn = self._conn
        self._conn = None
        await conn.close()

    async def get_connection(self) -> AsyncConnection:
        if self._conn is None or self._conn.closed:
            self._conn = await AsyncConnection.connect(self.CONNINFO)
        return self._conn


def fetch(func):
    async def wrapper(self, *args):
        db = await OldDatabase.connect()
        conn = await db.get_connection()
        async with conn.cursor() as cursor:
            await func(self, cursor, *args)

        await conn.close()

    return wrapper


def migration(func):
    def wrapper(self):
        db = BotDatabase()
        cursor = db.get_cursor()
        func(self, cursor)

        cursor.close()

    return wrapper


class Migrator:
    def __init__(self):
        self.data = None

    @migration
    def migrate_userdata(self, cursor):
        cursor.execute("SELECT userid, username, money, receive, autoafk FROM userdata")
        users = cursor.fetchall()

        User.objects.bulk_create([
            User(id=user[0], username=user[1], money=user[2], can_receive_money=user[3], auto_remove_afk=user[4])
            for user in users
        ])

    @fetch
    async def fetch_users(self, cursor):
        await cursor.execute("SELECT twitch_id, twitch_name, osu_id, osu_username FROM main_user")
        self.data = await cursor.fetchall()

    def insert_users(self):
        for user in self.data:
            obj = User.objects.filter(id=user[0]).first()
            if obj is None:
                User.objects.create(id=user[0], username=user[1])

        UserOsuData.objects.bulk_create([
            UserOsuData(user_id=user[0], id=user[2], username=user[3], global_rank=0)
            for user in self.data if user[2] is not None
        ])

    @fetch
    async def fetch_placements(self, cursor, limit, offset):
        await cursor.execute("SELECT timestamp, x, y, color, main_user.twitch_id FROM place_placement LEFT JOIN main_user ON (main_user.id = place_placement.user_id) LIMIT %s OFFSET %s", (limit, offset))
        self.data = await cursor.fetchall()

    def insert_placements(self):
        Placement.objects.bulk_create([
            Placement(timestamp=placement[0], x=placement[1], y=placement[2], color=placement[3], user_id=placement[4])
            for placement in self.data
        ])

        self.data = None

    @migration
    def migrate_afks(self, cursor):
        cursor.execute("SELECT message, time, username FROM afk")
        afks = cursor.fetchall()

        for afk in afks:
            user = User.objects.filter(username=afk[2]).first()
            if user is not None:
                UserAfk.objects.create(user=user, msg=afk[0], timestamp=datetime.fromisoformat(afk[1]).timestamp() // 1)

    @migration
    def migrate_ac_games(self, cursor):
        cursor.execute("SELECT user, score, finished FROM animecompare_games")
        games = cursor.fetchall()

        for game in games:
            user = User.objects.filter(username=game[0]).first()
            if user is not None:
                AnimeCompareGame.objects.create(user=user, score=game[1], is_finished=game[2])

    @migration
    def migrate_channels(self, cursor):
        cursor.execute("SELECT name, id, offlineonly FROM channels")
        channels = cursor.fetchall()

        for channel in channels:
            user = User.objects.filter(id=channel[1]).first()
            if user is None:
                user = User.objects.create(id=channel[1], username=channel[0])

            UserChannel.objects.create(user=user, is_offline_only=channel[2])

    @migration
    def migrate_lastfm(self, cursor):
        cursor.execute("SELECT user_id, lastfm_user FROM lastfm")
        UserLastFM.objects.bulk_create([
            UserLastFM(user_id=lastfm[0], username=lastfm[1])
            for lastfm in cursor.fetchall()
        ])

    @migration
    def migrate_osu_data(self, cursor):
        cursor.execute("SELECT osu_user_id, osu_username, verified, user_id FROM osu_data")
        osu_data = cursor.fetchall()

        for data in osu_data:
            user = User.objects.filter(id=data[3]).first()
            if user is None:
                continue

            try:
                UserOsuData.objects.create(id=data[0], username=data[1], global_rank=0)
            except:  # constraint violation
                continue

            UserOsuConnection.objects.create(user=user, osu_id=data[0], is_verified=data[2])

    @migration
    def migrate_pity(self, cursor):
        cursor.execute("SELECT username, four, five FROM pity")
        pities = cursor.fetchall()

        users = list(User.objects.filter(username__in=[pity[0] for pity in pities]))
        for user in users:
            pity = next((pity for pity in pities if pity[0] == user.username))
            UserPity.objects.create(user=user, four=pity[1], five=pity[2])

    @migration
    def migrate_reminders(self, cursor):
        cursor.execute("SELECT user_id, end_time, message, channel FROM reminders")
        reminders = cursor.fetchall()

        for reminder in reminders:
            user = User.objects.filter(id=reminder[0]).first()
            if user is None:
                continue

            channel = UserChannel.objects.filter(user__username=reminder[3]).first()
            if channel is None:
                continue

            UserReminder.objects.create(user=user, channel=channel, remind_at=datetime.fromisoformat(reminder[1]).timestamp() // 1, message=reminder[2])

    @migration
    def migrate_timezones(self, cursor):
        cursor.execute("SELECT userid, timezone from timezones")
        timezones = cursor.fetchall()

        for timezone in timezones:
            user = User.objects.filter(id=timezone[0]).first()
            if user is None:
                continue

            UserTimezone.objects.create(user=user, timezone=timezone[1])


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.new_event_loop()

    migrator = Migrator()

    print("migrating userdata")
    migrator.migrate_userdata()

    print("migrating users")
    loop.run_until_complete(migrator.fetch_users())
    migrator.insert_users()

    print("migrating placement")
    for i in range(6):
        loop.run_until_complete(migrator.fetch_placements(100000, i*100000))
        migrator.insert_placements()

    loop.close()

    print("migrating afks")
    migrator.migrate_afks()

    print("migrating ac games")
    migrator.migrate_ac_games()

    print("migrating channels")
    migrator.migrate_channels()

    print("migrating lastfm")
    migrator.migrate_lastfm()

    print("migrating osu data")
    migrator.migrate_osu_data()

    print("migrating pity")
    migrator.migrate_pity()

    print("migrating reminders")
    migrator.migrate_reminders()

    print("migrating timezones")
    migrator.migrate_timezones()
