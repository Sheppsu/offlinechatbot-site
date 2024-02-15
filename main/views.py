from django.shortcuts import redirect
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseServerError, HttpResponseBadRequest, Http404
from django.contrib.auth import get_user_model, login as _login, logout as _logout
from django.conf import settings

from sesame.utils import get_token as _get_token
from common.util import render, get_database
from common.constants import AUTH_BACKEND
import traceback
import requests
from osu import Client, AuthHandler, Scope


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
        return redirect(state or "index")
    except requests.HTTPError as exc:
        print(exc)
        return HttpResponseBadRequest()
    except:
        traceback.print_exc()
    return HttpResponseServerError()


def set_osu_data_verified(user):
    db = get_database()
    cursor = db.cursor()
    cursor.execute(f"SELECT osu_user_id FROM osu_data WHERE user_id = {user.twitch_id}")
    if cursor.fetchone():
        cursor.execute(f"UPDATE osu_data SET osu_user_id = {user.osu_id}, osu_username = '{user.osu_username}', verified = 1 WHERE user_id = {user.twitch_id!r}")
    else:
        cursor.execute(f"INSERT INTO osu_data (osu_user_id, osu_username, verified) VALUES ({user.osu_id}, '{user.osu_username}', 1)")
    db.commit()


def handle_osu_auth(req, code):
    auth_handler = AuthHandler(
        settings.OSU_CLIENT_ID,
        settings.OSU_CLIENT_SECRET,
        settings.OSU_CLIENT_REDIRECT,
        Scope.identify()
    )
    auth_handler.get_auth_token(code)
    client = Client(auth_handler)
    user = client.get_own_data()
    req.user.osu_id = user.id
    req.user.osu_username = user.username
    req.user.save()
    set_osu_data_verified(req.user)
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
    except requests.HTTPError as exc:
        print(exc)
        return HttpResponseBadRequest()


def login_info(req):
    if not req.user.is_authenticated:
        raise Http404()
    return HttpResponse(f"Twitch username: {req.user.twitch_name}<br/>"
                        f"Twitch user id: {req.user.twitch_id}<br/>"
                        f"osu! username: {req.user.osu_username}<br/>"
                        f"osu! id: {req.user.osu_id}")


def logout(req):
    if req.user.is_authenticated:
        _logout(req)
    state = req.GET.get("state", None)
    return redirect(state or "index")


def get_token(req):
    if req.user.is_authenticated:
        return HttpResponse("{\"token\": \"%s\"}" % _get_token(req.user))
    return HttpResponseForbidden("{\"error\": \"You are not logged in\"}")
