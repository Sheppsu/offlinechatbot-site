from django.shortcuts import render as _render

from common.twitch_api import get_auth_url


def render(request, template_name, context=None, *args, **kwargs):
    if context is None:
        context = {}

    context["user"] = request.user
    context["auth_url"] = get_auth_url(request.path)
    context["state"] = request.path
    return _render(request, template_name, context, *args, **kwargs)
