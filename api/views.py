from django.http import JsonResponse

from main.models import Command, UserChannel

import socket
import json
import os
import threading
import queue


class BotCommunicator:
    SERVER_PORT = int(os.getenv("SERVER_PORT"))

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._running: threading.Event = threading.Event()
        self._lock = threading.Lock()

    def put(self, channel_id: int):
        self._lock.acquire()

        self._queue.put(channel_id)

        if not self._running.is_set():
            threading.Thread(target=self.run)
            self._running.wait()

        self._lock.release()

    def _refresh_channel_for_bot(self, channel_id):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('127.0.0.1', self.SERVER_PORT))
            s.send(json.dumps({"cmd": 0, "channel_id": channel_id}).encode('utf-8'))
            s.close()
        except ConnectionRefusedError:
            return

    def run(self):
        self._running.set()

        while True:
            channel_id = self._queue.get()

            if channel_id == 0:
                break

            self._refresh_channel_for_bot(channel_id)

        self._running.clear()


communicator = BotCommunicator()


def success(data, status=200):
    return JsonResponse({"data": data}, status=status, safe=False)


def error(msg, status=400):
    return JsonResponse({"error": msg}, status=status, safe=False)


def requires_channel(func):
    def wrapper(req, id, *args, **kwargs):
        if not req.user.is_authenticated:
            return error("not logged in", status=403)

        channel = UserChannel.objects.select_related("user").prefetch_related("managers").filter(id=id).first()
        if channel is None:
            return error("invalid channel id")

        if (
            channel.user.id != req.user.id and
            next((manager for manager in channel.managers if manager.id == req.user.id), None) is None
        ):
            return error("invalid permissions for this channel", status=403)

        return func(req, channel, *args, **kwargs)

    return wrapper


def requires_method(*methods: str):
    methods = list(map(str.lower, methods))  # type: ignore

    def decorator(func):
        def wrapper(req, *args, **kwargs):
            if req.method.lower() not in methods:
                return error("invalid method", status=405)

            return func(req, *args, **kwargs)

        return wrapper

    return decorator


def requires_data(func):
    def wrapper(req, *args, **kwargs):
        try:
            return func(req, *args, data=json.loads(req.body.decode('utf-8')), **kwargs)
        except json.decoder.JSONDecodeError:
            return error("invalid json body")

    return wrapper


def get_commands(req):
    return success([cmd.serialize() for cmd in Command.objects.all()])


@requires_channel
@requires_data
@requires_method("PATCH")
def update_channel_setting(req, channel: UserChannel, data):
    try:
        setting = data["setting"]
        value = data["value"]
        assert isinstance(setting, str)
        assert isinstance(value, bool)
    except (KeyError, AssertionError):
        return error("invalid data")

    try:
        setattr(channel, setting, value)
        channel.save()
    except KeyError:
        return error("invalid setting name")

    communicator.put(channel.id)

    return success(None)


def toggle_command(req):
    pass
