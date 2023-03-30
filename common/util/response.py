from django.shortcuts import render as _render

from .twitch_api import get_auth_url


def render(request, template_name, context=None, *args, **kwargs):
    if context is None:
        context = {}
    context["is_authenticated"] = request.user.is_authenticated
    context["is_mod"] = request.user.is_mod if request.user.is_authenticated else None
    context["is_admin"] = request.user.is_admin if request.user.is_authenticated else None
    context["is_banned"] = request.user.banned if request.user.is_authenticated else None
    context["auth_url"] = get_auth_url(request.path)
    context["state"] = request.path
    return _render(request, template_name, context, *args, **kwargs)
