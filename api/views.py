from django.http import JsonResponse

from main.models import Command

import socket
import json
import os


SERVER_PORT = os.getenv("SERVER_PORT")


def refresh_channel_for_bot(channel_id: int):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', SERVER_PORT))
    s.send(json.dumps({"cmd": 0, "channel_id": channel_id}).encode('utf-8'))
    s.close()


def success(data, status=200):
    return JsonResponse({"data": data}, status=status, safe=False)


def get_commands(req):
    return success([cmd.serialize() for cmd in Command.objects.all()])


def toggle_command(req):
    pass
