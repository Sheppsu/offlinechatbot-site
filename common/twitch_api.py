from django.conf import settings

import requests


REDIRECT_URI = "http://localhost:8001/login" if settings.DEBUG else "https://bot.sheppsu.me/login"


def get_auth_url(state=""):
    return f"https://id.twitch.tv/oauth2/authorize?client_id={settings.TWITCH_CLIENT_ID}&" \
           f"redirect_uri={REDIRECT_URI}&response_type=code&scope=&state={state}"


def get_auth_header(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": settings.TWITCH_CLIENT_ID,
    }


def get_token(code):
    params = {
        "client_id": settings.TWITCH_CLIENT_ID,
        "client_secret": settings.TWITCH_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }
    resp = requests.post("https://id.twitch.tv/oauth2/token", params=params)
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"]


def get_user(access_token):
    headers = get_auth_header(access_token)
    resp = requests.get("https://api.twitch.tv/helix/users", headers=headers)
    resp.raise_for_status()
    return resp.json()["data"][0]
