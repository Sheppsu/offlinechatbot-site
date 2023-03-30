from django.shortcuts import redirect
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseServerError
from django.contrib.auth import get_user_model, login as _login, logout as _logout

from sesame.utils import get_token as _get_token
from common.util import render
from common.constants import AUTH_BACKEND
import traceback


User = get_user_model()


def index(req):
    return render(req, 'main/index.html')


def login(req):
    try:
        code = req.GET.get("code", None)
        if code is not None:
            user = User.objects.create_user(code)
            _login(req, user, backend=AUTH_BACKEND)
        state = req.GET.get("state", None)
        return redirect(state or "index", permanent=True)
    except:
        traceback.print_exc()
    return HttpResponseServerError()


def logout(req):
    if req.user.is_authenticated:
        _logout(req)
    state = req.GET.get("state", None)
    return redirect(state or "index", permanent=True)


def get_token(req):
    if req.user.is_authenticated:
        return HttpResponse("{\"token\": \"%s\"}" % _get_token(req.user))
    return HttpResponseForbidden("{\"error\": \"You are not logged in\"}")
