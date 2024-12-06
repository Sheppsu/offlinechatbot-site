from django.shortcuts import redirect
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseServerError, HttpResponseBadRequest, Http404
from django.contrib.auth import get_user_model, login as _login, logout as _logout
from django.conf import settings

from common.views import render
from common.constants import AUTH_BACKEND
from .models import UserOsuConnection, UserOsuData

from sesame.utils import get_token as _get_token
from osu import Client, AuthHandler, Scope
import requests


User = get_user_model()


def index(req):
    return render(req, 'main/index.html')


def dashboard(req):
    return render(req, 'main/dashboard.html')


def login(req):
    try:
        code = req.GET.get("code", None)
        if code is not None:
            user = User.objects.create_user(code)
            _login(req, user, backend=AUTH_BACKEND)

        state = req.GET.get("state", None)
        return redirect(state or "index")
    except requests.HTTPError:
        return HttpResponseBadRequest()


def handle_osu_auth(req, code):
    auth_handler = AuthHandler(
        settings.OSU_CLIENT_ID,
        settings.OSU_CLIENT_SECRET,
        settings.OSU_CLIENT_REDIRECT,
        Scope.identify()
    )
    auth_handler.get_auth_token(code)
    client = Client(auth_handler)
    osu_user = client.get_own_data()

    UserOsuData.objects.update_or_create(
        id=osu_user.id,
        defaults={"username": osu_user.username, "global_rank": osu_user.statistics.global_rank}
    )
    UserOsuConnection.objects.update_or_create(
        user_id=req.user.id,
        defaults={"osu_id": osu_user.id, "is_verified": True}
    )

    state = req.GET.get("state", None)
    return redirect(state or "index")


def osu_auth(req):
    if not req.user.is_authenticated:
        return redirect("index")

    try:
        code = req.GET.get("code", None)
        if code is not None:
            return handle_osu_auth(req, code)

        return redirect(settings.OSU_AUTH_URL+"&state=login_info")
    except requests.HTTPError:
        return HttpResponseBadRequest()


def logout(req):
    if req.user.is_authenticated:
        _logout(req)

    state = req.GET.get("state", None)
    return redirect(state or "index")


def get_token(req):
    if req.user.is_authenticated:
        return HttpResponse("{\"token\": \"%s\"}" % _get_token(req.user))

    return HttpResponseForbidden("{\"error\": \"You are not logged in\"}")
