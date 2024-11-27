from django.contrib.auth import get_user_model

from common.views import render

User = get_user_model()


def canvas(req):
    return render(req, "place/index.html")


def leaderboard(req):
    users = list(
        sorted(
            filter(
                lambda u: u.blocks_placed > 0,
                User.objects.all()
            ),
            key=lambda u: u.blocks_placed,
            reverse=True
        )
    )
    return render(req, "place/leaderboard.html", context={"users": users})
