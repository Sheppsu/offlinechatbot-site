from django.shortcuts import redirect
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, Http404
from django.contrib.auth import get_user_model, login as _login, logout as _logout
from django.conf import settings

from common.views import render
from common.constants import AUTH_BACKEND
from .models import UserOsuConnection, UserOsuData, UserChannel, UserChannelConnection

from sesame.utils import get_token as _get_token
from osu import Client, AuthHandler, Scope
import requests


User = get_user_model()


def requires_login(func):
    def wrapper(req, *args, **kwargs):
        if not req.user.is_authenticated:
            return redirect("index")

        return func(req, *args, **kwargs)

    return wrapper


def index(req):
    return render(req, 'main/index.html')


@requires_login
def dashboard(req):
    osu = UserOsuConnection.objects.select_related("osu").filter(user_id=req.user.id).first()
    channel = UserChannel.objects.filter(user_id=req.user.id).first()
    if channel is not None:
        channel.user = req.user

    connections = UserChannelConnection.objects.select_related("channel__user").filter(user_id=req.user.id)

    return render(
        req,
        'main/dashboard.html',
        {
            "connections": {"osu": osu},
            "channels": ([channel] if channel is not None else []) + list((conn.channel for conn in connections)),
            "osu_auth_url": settings.OSU_AUTH_URL
        }
    )


@requires_login
def channel_dashboard(req, id: int):
    channel = UserChannel.objects.prefetch_related("commands__command", "managers").select_related("user").filter(id=id).first()
    if channel is None:
        return redirect("dashboard")

    if not channel.can_access_settings(req.user):
        return HttpResponseForbidden()

    serial_channel = channel.serialize(includes=["user", "commands__command"])
    serial_channel["commands"] = sorted(serial_channel["commands"], key=lambda c: c["command"]["name"])
    serial_channel["managers_string"] = ", ".join((conn.user.username for conn in channel.managers.all()))

    return render(
        req,
        "main/channel_dashboard.html",
        {"channel": serial_channel}
    )


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


@requires_login
def osu_auth(req):
    try:
        code = req.GET.get("code", None)
        if code is not None:
            handle_osu_auth(req, code)

        return redirect("dashboard")
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
