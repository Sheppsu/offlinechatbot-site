from django.db import models

from common.twitch_api import get_token, get_user
from common.models import enum_field


class UserPermissions(models.TextChoices):
    MODERATOR = 1 << 0
    ADMIN = 1 << 1


@enum_field(UserPermissions, models.PositiveSmallIntegerField)
class UserPermissionsField:
    pass


class UserManager(models.Manager):
    def create_user(self, code, permissions: UserPermissions | int = 0):
        access_token = get_token(code)
        twitch_user = get_user(access_token)
        try:
            user = User.objects.get(id=twitch_user["id"])
            user.username = twitch_user["login"]
            user.permissions = permissions
        except User.DoesNotExist:
            settings = UserSettings()
            settings.save()
            user = User(
                id=twitch_user["id"],
                username=twitch_user["login"],
                settings=settings,
                permissions=permissions
            )
        user.save()
        return user

    def create_superuser(self, code):
        return self.create_user(code, UserPermissions.ADMIN)


class UserSettings(models.Model):
    auto_remove_afk = models.BooleanField(default=False)
    can_receive_money = models.BooleanField(default=True)


class User(models.Model):
    is_anonymous = False
    is_authenticated = True

    id = models.PositiveIntegerField(primary_key=True, unique=True, db_index=True)
    username = models.CharField(max_length=25)
    permissions = UserPermissionsField(null=True, default=None)

    money = models.BigIntegerField(default=0)
    settings = models.ForeignKey(UserSettings, on_delete=models.PROTECT)
    osu = models.ForeignKey("UserOsuData", on_delete=models.SET_NULL, null=True)
    afk = models.ForeignKey("UserAfk", on_delete=models.SET_NULL, null=True)
    timezone = models.ForeignKey("UserTimezone", on_delete=models.SET_NULL, null=True)

    USERNAME_FIELD = "id"
    EMAIL_FIELD = None
    REQUIRED_FIELDS = [
        "username"
    ]

    objects = UserManager()

    def __str__(self):
        return self.username


class UserAfk(models.Model):
    msg = models.CharField(max_length=512)
    timestamp = models.DateTimeField()


class UserReminder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    channel = models.ForeignKey("Channel", on_delete=models.CASCADE)
    remind_at = models.DateTimeField()
    message = models.TextField()


class UserTimezone(models.Model):
    timezone = models.CharField(max_length=64)


class UserOsuData(models.Model):
    id = models.PositiveBigIntegerField(primary_key=True)
    username = models.CharField(max_length=19)
    global_rank = models.PositiveIntegerField()


class AnimeCompareGame(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.SmallIntegerField()
    is_finished = models.BooleanField()


class Channel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_offline_only = models.BooleanField()


class Command(models.Model):
    name = models.CharField(max_length=32)
    description = models.CharField(max_length=1024)
    aliases = models.JSONField(default=list)


class ChannelCommand(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    command = models.ForeignKey(Command, on_delete=models.CASCADE)
    is_enabled = models.BooleanField()
