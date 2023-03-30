from common.util import render


def overview(req):
    return render(req, "docs/index.html")
