import asyncio
import django
import websockets
import os
from time import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Union
from dotenv import load_dotenv
from functools import partial
import logging

load_dotenv()
os.environ["DJANGO_SETTINGS_MODULE"] = "offlinechatbot.settings"
django.setup()

from django.contrib.auth import get_user_model
from django.db import connection
from sesame.utils import get_user as _get_user

from place.models import Placement


UserModel = get_user_model()
_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s")
ch.setFormatter(formatter)
_log.addHandler(ch)

CANVAS_WIDTH = 750
CANVAS_HEIGHT = 750


class User:
    is_authenticated = True
    is_mod: bool
    is_admin: bool
    can_mod: bool
    banned: bool

    __slots__ = ("id", "name", "last_placement", "is_mod", "is_admin", "can_mod", "banned")

    def __init__(self, user: UserModel):
        self.id = user.id
        self.name = user.twitch_name
        self.last_placement = user.last_placement
        self.update(user)

    def update(self, user):
        self.is_mod = user.is_mod
        self.is_admin = user.is_admin
        self.can_mod = user.can_mod
        self.banned = user.banned

    def on_place(self):
        self.last_placement = time()
        user = self.get_object()
        user.blocks_placed += 1
        user.last_placement = self.last_placement
        self.update(user)
        user.save()

    def can_place(self, cooldown):
        return not (self.banned or time() - self.last_placement < cooldown)

    @property
    def can_clear(self):
        return self.can_mod

    @property
    def can_ban(self):
        return self.can_mod

    @property
    def can_set_cooldown(self):
        return self.can_mod

    @property
    def can_clear_user(self):
        return self.can_mod

    def get_object(self):
        return UserModel.objects.get(id=self.id)


class AnonymousUser:
    is_authenticated = False


class WebsocketWrapper:
    def __init__(self, ws, user: "USER_TYPE"):
        self.ws = ws
        self.user: USER_TYPE = user
        self.last_message = ""

    def __getattr__(self, item):
        return getattr(self.ws, item)

    async def send(self, msg, log=True):
        if log and type(msg) == str and msg != "PONG" and len(msg) < 1000:
            _log.info(f"Sending to {self.ws.id}: {msg}")

        await self.ws.send(msg)
        
    async def recv(self, do_check=False):
        msg = await self.ws.recv()
        if do_check and self.last_message.lower() == msg.lower():
            return None
        self.last_message = msg
        return self.last_message


USER_TYPE = Union[User, AnonymousUser]


class Canvas:
    def __init__(self):
        self.lock: threading.Lock = threading.Lock()

        self.canvas_cache = None
        self.user_cache = None

    @staticmethod
    def create_placement(user, x, y, c, timestamp=None):
        return {
            "timestamp": timestamp or time(),
            "user": user,
            "coordinate": [x, y],
            "color": c,
        }

    def _update_cache(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (x, y) (
                    x,
                    y,
                    color,
                    main_user.twitch_name
                ) FROM place_placement
                INNER JOIN main_user ON (main_user.id = place_placement.user_id)
                """
            )
            placements = cursor.fetchall()
        self.canvas_cache = bytearray(CANVAS_WIDTH*CANVAS_HEIGHT)
        users = ["" for _ in range(CANVAS_WIDTH*CANVAS_HEIGHT)]
        for placement in placements:
            placement = placement[0][1:-1].split(",")
            i = int(placement[0]) + int(placement[1]) * 750
            try:
                users[i] = placement[3]
                self.canvas_cache[i] = int(placement[2])
            except IndexError:
                continue
        self.user_cache = " ".join(users)

    def reset_cache(self):
        self.canvas_cache = None
        self.user_cache = None

    def get_canvas_info(self):
        self.lock.acquire()
        if self.canvas_cache is None or self.user_cache is None:
            self._update_cache()
        self.lock.release()
        return self.canvas_cache, self.user_cache

    # TODO: fix later (cuz no longer using mongodb)

    def get_last_pixel(self, x, y):
        self.lock.acquire()
        placement = self.db.placements.find_one({"coordinate": [x, y]}, sort=[('timestamp', -1)])
        self.lock.release()
        return placement

    def place_pixel(self, user: User, x: int, y: int, c: int):
        self.lock.acquire()
        self.db.placements.insert_one(self.create_placement(user.name, x, y, c))
        self.reset_cache()
        self.lock.release()

    def clear_canvas(self, x1: int, y1: int, x2: int, y2: int):
        self.lock.acquire()
        timestamp = time()
        self.db.placements.insert_many(sum([
            [self.create_placement("", x, y, 0, timestamp)
             for y in range(y1, y2+1)]
            for x in range(x1, x2+1)], []))
        self.reset_cache()
        self.lock.release()

    def clear_user(self, user):
        self.lock.acquire()
        self.db.placements.delete_many({"user": user})
        self.reset_cache()
        self.lock.release()


class Server:
    DEFAULT_COOLDOWN = 0

    def __init__(self):
        self.cooldown = self.DEFAULT_COOLDOWN
        self.executor = ThreadPoolExecutor()
        self.loop = asyncio.get_event_loop()
        self.canvas = Canvas()
        self.connections = {}
        self.user_lock = threading.Lock()
        self.commands = {
            # "PLACE": self.handle_place,
            # "AUTH": self.handle_authentication,
            # "CLEAR": self.handle_clear,
            # "BAN": self.handle_ban,
            "PING": self.handle_ping,
            # "SETCOOLDOWN": self.handle_set_cooldown,
            # "CLEARUSER": self.handle_clear_user,
        }
        self.last_place = None

    async def send_canvas_info(self, ws):
        """event loop safe"""
        canvas, users = await self.loop.run_in_executor(self.executor, self.canvas.get_canvas_info)
        await ws.send(canvas)
        await ws.send("USERS "+users)

    def get_user(self, token) -> Union[str, UserModel]:
        """not event loop safe"""
        # not so sure about the thread-safety of calling _get_user
        self.user_lock.acquire()
        user = _get_user(token)
        self.user_lock.release()
        if user is None:
            return "AUTHENTICATION FAILED"
        return user

    async def send_all(self, message, exclude=None):
        if exclude is None:
            exclude = []

        _log.info(f"Sending {message} to all")

        for ws in tuple(filter(lambda ws: ws.id not in exclude, self.connections.values())):
            await ws.send(message, log=False)

    def get_same_users(self, user_id):
        """event loop safe"""
        return tuple(filter(lambda other_ws: other_ws.user.is_authenticated and
                                       other_ws.user.id == user_id,
                      self.connections.values()))

    # Events
    # All events are event loop safe

    async def handle_authentication(self, ws, args):
        if ws.user.is_authenticated:
            return "ALREADY AUTHENTICATED"
        if len(args) < 1:
            return "INVALID"
        result = await self.loop.run_in_executor(self.executor, self.get_user, args[0])
        if type(result) == str:
            return result
        elif result.banned:
            return "FORBIDDEN"

        connected_elsewhere = False
        for other_ws in self.get_same_users(result.id):
            connected_elsewhere = True
            ws.user = other_ws.user
            break
        if not connected_elsewhere:
            ws.user = User(result)

        await ws.send("AUTHENTICATION SUCCESS")
        if time() - ws.user.last_placement < self.cooldown:
            await ws.send(f"COOLDOWN {int((ws.user.last_placement+self.cooldown)*1000)}")

    async def handle_clear(self, ws, args):
        if not ws.user.is_authenticated or not ws.user.can_clear:
            return "FORBIDDEN"
        if len(args) != 4:
            return "INVALID"
        try:
            coords = tuple(map(int, args))
        except ValueError:
            return "INVALID"
        x1, y1, x2, y2 = coords
        if x2 - x1 < 0 or y2 - y1 < 0:
            return "INVALID"
        if not (0 <= x1 < CANVAS_WIDTH and 0 <= x2 < CANVAS_WIDTH) or not (0 <= y1 < CANVAS_HEIGHT and 0 <= y2 < CANVAS_HEIGHT):
            return "INVALID"
        await self.loop.run_in_executor(self.executor, self.canvas.clear_canvas, x1, y1, x2, y2)
        print(f"{ws.user.name} cleared from ({x1}, {y1}) to ({x2}, {y2})")
        event = f"CLEAR {x1} {y1} {x2} {y2}"
        await ws.send(event)  # prioritize user that sent the command
        await self.send_all(event, [ws.id])

    async def handle_place(self, ws, args):
        if not ws.user.is_authenticated or not ws.user.can_place(self.cooldown):
            return "FORBIDDEN"
        if len(args) != 3:
            return "INVALID"
        try:
            x, y, c = tuple(map(int, args))
        except ValueError:
            return "INVALID"
        if c > 39 or not 0 <= x < CANVAS_WIDTH or not 0 <= y < CANVAS_HEIGHT:
            return "INVALID"
        last_placement = await self.loop.run_in_executor(self.executor, self.canvas.get_last_pixel, x, y)
        if last_placement and last_placement["user"] == ws.user.name and last_placement["color"] == c:
            return "FORBIDDEN"
        await self.loop.run_in_executor(self.executor, self.canvas.place_pixel, ws.user, x, y, c)
        await self.loop.run_in_executor(self.executor, ws.user.on_place)
        print(f"{ws.user.name} placed {c} at ({x}, {y})")
        event = f"PLACE {ws.user.name} {x} {y} {c}"
        self.last_place = ws.user.id
        await ws.send(event)
        if self.cooldown > 0:
            for other_ws in self.get_same_users(ws.user.id):
                await other_ws.send(f"COOLDOWN {int((ws.user.last_placement+self.cooldown)*1000)}")
        await self.send_all(event, [ws.id])

    async def handle_ban(self, ws, args):
        if not ws.user.is_authenticated or not ws.user.can_ban:
            return "FORBIDDEN"
        if len(args) < 1:
            return "INVALID"
        try:
            user = await self.loop.run_in_executor(self.executor, partial(UserModel.objects.get, twitch_name=args[0].lower()))
        except UserModel.DoesNotExist:
            return "INVALID"
        if user.banned:
            return
        if user.can_mod:
            return "FORBIDDEN"
        user.banned = True
        await self.loop.run_in_executor(self.executor, user.save)
        for ws in self.get_same_users(user.id):
            await ws.send("BANNED")

    async def handle_ping(self, ws, args):
        await ws.send("PONG")

    async def handle_set_cooldown(self, ws, args):
        if not ws.user.is_authenticated or not ws.user.can_set_cooldown:
            return "FORBIDDEN"
        if len(args) < 1:
            return "INVALID"
        try:
            self.cooldown = int(args[0])
        except ValueError:
            return "INVALID"
        for ws in tuple(self.connections.values()):
            if (now := time()) - ws.user.last_placement < self.cooldown:
                await self.send_all(f"COOLDOWN {ws.user.last_placement + self.cooldown}")

    async def handle_clear_user(self, ws, args):
        if not ws.user.is_authenticated or not ws.user.can_clear_user:
            return "FORBIDDEN"
        if len(args) < 1:
            return "INVALID"
        await self.loop.run_in_executor(self.executor, self.canvas.clear_user, args[0])
        if self.canvas.canvas_cache is None:
            # Not using websockets.broadcast because it does not use fragmenting and this is sizeable data
            canvas, users = await self.loop.run_in_executor(self.executor, self.canvas.get_canvas_info)
            for ws in tuple(self.connections.values()):
                await ws.send(canvas)
                await ws.send(users)

    # Event functionality

    async def handle_command(self, ws, command):
        if command.lower() != "ping":
            _log.info(f"{ws.id}: {command}")
        command = command.split()
        if len(command) < 1:
            return await ws.send("INVALID")
        command, args = command[0], command[1:]
        if command.upper() in self.commands:
            result = await self.commands[command.upper()](ws, args)
            if result is not None:
                await ws.send(result)
            return
        return await ws.send("INVALID")

    async def handler(self, ws):
        self.connections[ws.id] = (ws := WebsocketWrapper(ws, AnonymousUser()))
        _log.info(f"Opened connection with {ws.id}")
        try:
            await self.send_canvas_info(ws)
            while True:
                command = await ws.recv(do_check=ws.user.is_authenticated and self.last_place == ws.user.id)
                if command is None:
                    continue
                await self.handle_command(ws, command)
        except (websockets.ConnectionClosed, websockets.ConnectionClosedOK):
            pass
        except Exception as exc:
            _log.exception("Error when handling websocket", exc_info=exc)
        finally:
            _log.info(f"Closed connection with {ws.id}")
            del self.connections[ws.id]

    async def run(self):
        async with websockets.serve(self.handler, os.getenv("HOST"), os.getenv("PORT")):
            _log.info("Server up!")
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    server = Server()
    server.loop.run_until_complete(server.run())
