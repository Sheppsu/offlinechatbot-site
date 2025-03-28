from django.conf import settings

import requests
import os
import traceback


WEBHOOK_URL = os.getenv("WEBHOOK_URL")


def header_embed():
    return dict({
        "title": "Headers",
        "fields": list(),
        "color": 0x0000ff
    })


def send_error_embed(req, exc):
    embeds = [
        {
            "description": block,
            "color": 0xff0000,
        }
        for block in traceback.format_exception(exc)[1:]
    ]
    embeds[0]["title"] = f"{req.method} {req.path}"
    embeds.append(header_embed())

    for name, value in req.headers.items():
        if len(embeds[-1]["fields"]) == 25:
            embeds.append(header_embed())
        embeds[-1]["fields"].append({"name": name, "value": value})

    requests.post(WEBHOOK_URL, json={"embeds": embeds})


class ExceptionHandlingMiddleware:
    async_capable = False
    sync_capable = True

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, *args, **kwargs):
        return self.get_response(*args, **kwargs)

    def process_exception(self, req, exc):
        if not settings.DEBUG:
            send_error_embed(req, exc)
