from common.views import render


def overview(req):
    return render(req, "docs/index.html")
