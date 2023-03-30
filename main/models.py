from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

from common.util import get_tokens, get_user

import uuid


class UserType(models.TextChoices):
    USER = 1
    MODERATOR = 2
    ADMIN = 3


class UserManager(BaseUserManager):
    def create_user(self, code, type=UserType.USER):
        access_token, refresh_token = get_tokens(code)
        twitch_user = get_user(access_token)
        try:
            user = User.objects.get(twitch_id=twitch_user["id"])
            user.refresh_token = refresh_token
        except User.DoesNotExist:
            user = User(twitch_id=twitch_user["id"], twitch_name=twitch_user["login"],
                        refresh_token=refresh_token, type=type)
        user.save()
        return user

    def create_superuser(self, code):
        return self.create_user(code, type=UserType.ADMIN)


class User(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    twitch_id = models.PositiveIntegerField(unique=True, editable=False)
    twitch_name = models.CharField(max_length=25, unique=True)

    banned = models.BooleanField(default=False)
    type = models.IntegerField(choices=UserType.choices, default=UserType.USER)

    blocks_placed = models.PositiveIntegerField(default=0)
    last_placement = models.PositiveBigIntegerField(default=0)

    refresh_token = models.CharField(max_length=64, default="")

    USERNAME_FIELD = "twitch_name"
    EMAIL_FIELD = None
    REQUIRED_FIELDS = [
        "twitch_id",
    ]

    objects = UserManager()

    def __str__(self):
        return self.twitch_name

    @property
    def can_mod(self):
        return self.type >= int(UserType.MODERATOR)

    @property
    def is_mod(self):
        return self.type == int(UserType.MODERATOR)

    @property
    def is_admin(self):
        return self.type == int(UserType.ADMIN)
