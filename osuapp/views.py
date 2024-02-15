from common.util import render, get_database


def index(req):
    db = get_database()
    cursor = db.cursor()
    cursor.execute(
        "SELECT osu_user_data.osu_user_id, osu_data.osu_username, osu_user_data.global_rank FROM osu_user_data "
        "INNER JOIN osu_data ON osu_user_data.osu_user_id = osu_data.osu_user_id "
        "WHERE verified = 1"
    )
    verified_users = sorted(cursor.fetchall(), key=lambda u: u[2])

    def number(arr):
        for i in range(len(arr)):
            yield i+1, arr[i]

    return render(req, 'osuapp/index.html', context={"users": number(verified_users)})
