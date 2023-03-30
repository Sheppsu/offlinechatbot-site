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

load_dotenv()
os.environ["DJANGO_SETTINGS_MODULE"] = "offlinechatbot.settings"
django.setup()

from django.contrib.auth import get_user_model
from sesame.utils import get_user as _get_user


UserModel = get_user_model()
COOLDOWN = 10


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
        self.last_placement = round(current_time)
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

    def __getattr__(self, item):
        return getattr(self.ws, item)


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

    def update_cache(self):
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
        self.canvas_cache = bytearray(125000)
        users = ["" for _ in range(250000)]  # TODO: look into using numpy
        for item in canvas_info:
            users[item[0]] = item[1]
            self.canvas_cache[item[0] // 2] += item[2] if item[0] % 2 == 1 else item[2] << 4
        self.user_cache = " ".join(users)

    def reset_cache(self):
        self.canvas_cache = None
        self.user_cache = None

    def get_canvas_info(self):
        self.lock.acquire()
        if self.canvas_cache is None or self.user_cache is None:
            self.update_cache()
        self.lock.release()
        return self.canvas_cache, self.user_cache

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
        if user is None:
            return "AUTHENTICATION FAILED"
        self.user_lock.release()
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
            await ws.send(f"COOLDOWN {(ws.user.last_placement+COOLDOWN)*1000}")

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
        if not ws.user.is_authenticated or not await self.loop.run_in_executor(self.executor, ws.user.on_place):
            return "FORBIDDEN"
        if len(args) != 3:
            return "INVALID"
        try:
            x, y, c = tuple(map(int, args))
        except ValueError:
            return "INVALID"
        if c > 15:
            return "INVALID"
        await self.loop.run_in_executor(self.executor, self.canvas.place_pixel, ws.user, x, y, c)
        print(f"{ws.user.name} placed {c} at ({x}, {y})")
        event = f"PLACE {ws.user.name} {x} {y} {c}"
        await ws.send(event)
        for other_ws in self.get_same_users(ws.user.id):
            await other_ws.send(f"COOLDOWN {(ws.user.last_placement+COOLDOWN)*1000}")
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

    # Event functionality

    async def handle_command(self, ws, command):
        print(f"{ws.id}: {command}")
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
        print(f"Opened connection with {ws.id}")
        await self.send_canvas_info(ws)
        try:
            while True:
                command = await ws.recv()
                await self.handle_command(ws, command)
        except websockets.ConnectionClosed:
            print(f"Closed connection with {ws.id}")
        finally:
            del self.connections[ws.id]

    async def run(self):
        async with websockets.serve(self.handler, "0.0.0.0", 8727):
            print("Server up!")
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    server = Server()
    server.loop.run_until_complete(server.run())
