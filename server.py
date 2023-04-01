import asyncio
import django
import websockets
import pymongo
import os
from time import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Union, Optional
from dotenv import load_dotenv
from functools import partial
import logging
import math

load_dotenv()
os.environ["DJANGO_SETTINGS_MODULE"] = "offlinechatbot.settings"
django.setup()

from django.contrib.auth import get_user_model
from sesame.utils import get_user as _get_user


UserModel = get_user_model()
COOLDOWN = 0
_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s")
ch.setFormatter(formatter)
_log.addHandler(ch)


class User:
    is_authenticated = True
    is_mod: bool
    is_admin: bool
    can_mod: bool
    banned: bool

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
        if self.banned or (current_time := time()) - self.last_placement < COOLDOWN:
            return False
        self.last_placement = current_time
        user = self.get_object()
        user.blocks_placed += 1
        user.last_placement = self.last_placement
        self.update(user)
        user.save()
        return True

    def on_clear(self):
        if not self.can_mod:
            return False
        return True

    def on_ban(self):
        if not self.can_mod:
            return False
        return True

    def get_object(self):
        return UserModel.objects.get(id=self.id)


class AnonymousUser:
    is_authenticated = False


class WebsocketWrapper:
    def __init__(self, ws, user: "USER_TYPE"):
        self.ws = ws
        self.user: USER_TYPE = user
        self.last_message = None

    def __getattr__(self, item):
        return getattr(self.ws, item)

    async def send(self, msg):
        if type(msg) == str and msg != "PONG" and len(msg) < 1000:
            _log.info(f"Replying to {self.ws.id}: {msg}")
        await self.ws.send(msg)
        
    async def recv(self):
        msg = await self.ws.recv()
        if not self.on_message(msg):
            return
        return msg
        
    def on_message(self, msg):
        if self.last_message is not None and self.last_message.lower().strip() == msg.lower().strip():
            return False
        self.last_message = msg
        return True


USER_TYPE = Union[User, AnonymousUser]


class Canvas:
    def __init__(self):
        self.db: pymongo.MongoClient = pymongo.MongoClient(host=os.getenv("MONGO_URL")).place
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
        _log.info("Updating cache...")
        query = self.db.placements.aggregate([{"$group": {
            "_id": "$coordinate",
            "user": {"$last": "$user"},
            "color": {"$last": "$color"}
        }}])
        canvas_info = sorted(map(lambda p: (
            p["_id"][0] + p["_id"][1] * 500,
            p["user"],
            p["color"],
        ), query), key=lambda item: item[0])
        self.canvas_cache = bytearray(250000)
        users = ["" for _ in range(250000)]  # TODO: look into using numpy
        for item in canvas_info:
            if item[0] >= len(users):
                continue
            users[item[0]] = item[1]
            self.canvas_cache[item[0]] = item[2]
        self.user_cache = " ".join(users)
        _log.info("Cache updated!")

    def reset_cache(self):
        self.canvas_cache = None
        self.user_cache = None

    def get_canvas_info(self):
        self.lock.acquire()
        _log.info("Getting canvas info...")
        if self.canvas_cache is None or self.user_cache is None:
            self._update_cache()
        _log.info("Canvas info retrieved.")
        self.lock.release()
        return self.canvas_cache, self.user_cache

    def get_last_pixel(self, x, y):
        self.lock.acquire()
        placement = self.db.placements.find_one({"coordinate": [x, y]}, sort=[('timestamp', -1)])
        self.lock.release()
        return placement

    def place_pixel(self, user: User, x: int, y: int, c: int):
        self.lock.acquire()
        _log.info("Inserting placement...")
        self.db.placements.insert_one(self.create_placement(user.name, x, y, c))
        self.reset_cache()
        _log.info("Placement inserted")
        self.lock.release()

    def clear_canvas(self, x1: int, y1: int, x2: int, y2: int):
        self.lock.acquire()
        _log.info("Clearing canvas...")
        timestamp = time()
        self.db.placements.insert_many(sum([
            [self.create_placement("", x, y, 0, timestamp)
             for y in range(y1, y2+1)]
            for x in range(x1, x2+1)], []))
        self.reset_cache()
        _log.info("Canvas cleared.")
        self.lock.release()

    def clear_user(self, user):
        self.lock.acquire()
        _log.info("Clearing user placements...")
        self.db.placements.delete_many({"user": user})
        self.reset_cache()
        _log.info("User placements cleared.")
        self.lock.release()


class Server:
    def __init__(self):
        self.executor = ThreadPoolExecutor()
        self.loop = asyncio.get_event_loop()
        self.canvas = Canvas()
        self.connections = {}
        self.user_lock = threading.Lock()
        self.commands = {
            "PLACE": self.handle_place,
            "AUTH": self.handle_authentication,
            "CLEAR": self.handle_clear,
            "BAN": self.handle_ban,
            "PING": self.handle_ping,
        }

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
        for ws_id, ws in self.connections.items():
            if ws_id not in exclude:
                await ws.send(message)

    def get_same_users(self, user_id):
        """event loop safe"""
        return filter(lambda other_ws: other_ws.user.is_authenticated and
                                       other_ws.user.id == user_id,
                      self.connections.values())

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
        if time() - ws.user.last_placement < COOLDOWN:
            await ws.send(f"COOLDOWN {int((ws.user.last_placement+COOLDOWN)*1000)}")

    async def handle_clear(self, ws, args):
        if not ws.user.is_authenticated or not ws.user.on_clear():
            return "FORBIDDEN"
        if len(args) != 4:
            return "INVALID"
        try:
            coords = tuple(map(int, args))
        except ValueError:
            return "INVALID"
        if not all(map(lambda c: 0 <= c <= 499, coords)):
            return "INVALID"
        x1, y1, x2, y2 = coords
        if x2 - x1 < 0 or y2 - y1 < 0:
            return "INVALID"
        await self.loop.run_in_executor(self.executor, self.canvas.clear_canvas, x1, y1, x2, y2)
        print(f"{ws.user.name} cleared from ({x1}, {y1}) to ({x2}, {y2})")
        event = f"CLEAR {x1} {y1} {x2} {y2}"
        await ws.send(event)  # prioritize user that sent the command
        await self.send_all(event, [ws.id])

    async def handle_place(self, ws, args):
        if not ws.user.is_authenticated:
            return "FORBIDDEN"
        if len(args) != 3:
            return "INVALID"
        try:
            x, y, c = tuple(map(int, args))
        except ValueError:
            return "INVALID"
        if c > 35 or x < 0 or x > 499 or y < 0 or y > 499:
            return "INVALID"
        last_placement = await self.loop.run_in_executor(self.executor, self.canvas.get_last_pixel, x, y)
        if last_placement and last_placement["user"] == ws.user.name and last_placement["color"] == c:
            return "FORBIDDEN"
        if not await self.loop.run_in_executor(self.executor, ws.user.on_place):
            return "FORBIDDEN"
        await self.loop.run_in_executor(self.executor, self.canvas.place_pixel, ws.user, x, y, c)
        print(f"{ws.user.name} placed {c} at ({x}, {y})")
        event = f"PLACE {ws.user.name} {x} {y} {c}"
        await ws.send(event)
        # for other_ws in self.get_same_users(ws.user.id):
        #     await other_ws.send(f"COOLDOWN {int((ws.user.last_placement+COOLDOWN)*1000)}")
        await self.send_all(event, [ws.id])

    async def handle_ban(self, ws, args):
        if not ws.user.is_authenticated or not ws.user.on_ban():
            return "FORBIDDEN"
        if len(args) < 1:
            return "INVALID"
        try:
            user = await self.loop.run_in_executor(self.executor, partial(UserModel.objects.get, twitch_name=args[0].lower()))
        except UserModel.DoesNotExist:
            return "INVALID"
        if user.banned:
            return
        user.banned = True
        await self.loop.run_in_executor(self.executor, user.save)
        for ws in self.get_same_users(user.id):
            await ws.send("BANNED")

    async def handle_ping(self, ws, args):
        await ws.send("PONG")

    # Event functionality

    async def handle_command(self, ws, command):
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
        await self.send_canvas_info(ws)
        try:
            while True:
                command = await ws.recv()
                if command is None:
                    continue
                await self.handle_command(ws, command)
        except websockets.ConnectionClosed:
            _log.info(f"Closed connection with {ws.id}")
        finally:
            del self.connections[ws.id]

    async def run(self):
        async with websockets.serve(self.handler, os.getenv("HOST"), os.getenv("PORT")):
            _log.info("Server up!")
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    server = Server()
    server.loop.run_until_complete(server.run())
