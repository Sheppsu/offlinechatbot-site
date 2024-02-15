from schedule import Scheduler
import threading
import time

from common.util import get_database, batch
from django.conf import settings


def run_continuously(self, interval=1):
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                self.run_pending()
                time.sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.daemon = True
    continuous_thread.start()
    return cease_continuous_run


Scheduler.run_continuously = run_continuously


def start_scheduler():
    scheduler = Scheduler()
    scheduler.every(10).minute.do(update_osu_user_data).run()
    scheduler.run_continuously()


# jobs

def update_osu_user_data():
    print("aaaa")
    client = settings.OSU_CLIENT
    db = get_database()
    cursor = db.cursor()

    cursor.execute("SELECT osu_user_id FROM osu_data WHERE verified = 1")
    for user_ids in batch([user[0] for user in cursor.fetchall()], 50):
        users = client.get_users(user_ids)
        for user in users:
            rank = user.statistics_rulesets.osu.global_rank or 'null'
            cursor.execute(
                f"INSERT INTO osu_user_data (osu_user_id, global_rank) VALUES ({user.id}, {rank}) "
                f"ON DUPLICATE KEY UPDATE global_rank = {rank}"
            )
    db.commit()
