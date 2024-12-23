from django.db import models

from common.twitch_api import get_token, get_user
from common.models import enum_field
from common.serializer import SerializableModel

from enum import IntFlag


class UserPermissions(IntFlag):
    MODERATOR = 1 << 0
    ADMIN = 1 << 1


@enum_field(UserPermissions, models.PositiveSmallIntegerField)
class UserPermissionsField:
    pass


class UserManager(models.Manager):
    def create_user(self, code, permissions: UserPermissions | None = None):
        access_token = get_token(code)
        twitch_user = get_user(access_token)
        try:
            user = User.objects.get(id=twitch_user["id"])
            user.username = twitch_user["login"]
        except User.DoesNotExist:
            user = User(
                id=twitch_user["id"],
                username=twitch_user["login"],
                permissions=permissions
            )
        user.save()
        return user

    def create_superuser(self, code):
        return self.create_user(code, UserPermissions.ADMIN)


class User(SerializableModel):
    is_anonymous = False
    is_authenticated = True

    id = models.PositiveIntegerField(primary_key=True, unique=True, db_index=True)
    username = models.CharField(max_length=25)
    permissions = UserPermissionsField(null=True, default=None)

    money = models.BigIntegerField(default=0)

    # settings
    auto_remove_afk = models.BooleanField(default=False)
    can_receive_money = models.BooleanField(default=True)

    USERNAME_FIELD = "id"
    EMAIL_FIELD = None
    REQUIRED_FIELDS = [
        "username"
    ]

    objects = UserManager()

    @property
    def is_admin(self):
        return self.permissions is not None and UserPermissions.ADMIN in self.permissions

    class Serialization:
        FIELDS = ["id", "username", "permissions"]

    def __str__(self):
        return self.username


class UserChannel(SerializableModel):
    user = models.OneToOneField("User", on_delete=models.CASCADE)
    is_offline_only = models.BooleanField(default=True)
    is_enabled = models.BooleanField(default=False)

    def can_access_settings(self, user: User):
        """Accesses 'managers' o2m field"""
        if not user.is_authenticated:
            return False

        if user.is_admin:
            return True

        return (
            self.user_id == user.id or
            next((manager for manager in self.managers.all() if manager.user_id == user.id), None) is not None
        )

    class Serialization:
        FIELDS = ["id", "is_offline_only", "is_enabled"]


class UserChannelConnection(SerializableModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="managed_channels")
    channel = models.ForeignKey(UserChannel, on_delete=models.CASCADE, related_name="managers")

    class Serialization:
        FIELDS = ["id"]


class UserAfk(models.Model):
    user = models.OneToOneField("User", on_delete=models.CASCADE)
    msg = models.CharField(max_length=512)
    timestamp = models.PositiveBigIntegerField()


class UserTimezone(models.Model):
    user = models.OneToOneField("User", on_delete=models.CASCADE)
    timezone = models.CharField(max_length=64)


class UserOsuData(models.Model):
    id = models.PositiveBigIntegerField(primary_key=True)
    username = models.CharField(max_length=19)
    global_rank = models.PositiveIntegerField(null=True)


class UserOsuConnection(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    osu = models.ForeignKey(UserOsuData, on_delete=models.CASCADE)
    is_verified = models.BooleanField(default=False)


class UserLastFM(models.Model):
    user = models.OneToOneField("User", on_delete=models.CASCADE)
    username = models.CharField(max_length=36)


class UserPity(models.Model):
    user = models.OneToOneField("User", on_delete=models.CASCADE)
    four = models.PositiveSmallIntegerField(default=0)
    five = models.PositiveSmallIntegerField(default=0)


class UserReminder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reminders")
    channel = models.ForeignKey("UserChannel", on_delete=models.CASCADE)
    remind_at = models.PositiveBigIntegerField()
    message = models.CharField(max_length=512)


class AnimeCompareGame(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ac_games")
    score = models.SmallIntegerField()
    is_finished = models.BooleanField()


class Command(SerializableModel):
    name = models.CharField(max_length=32)
    description = models.CharField(max_length=1024)
    aliases = models.JSONField(default=list)
    args = models.JSONField(default=list)

    class Serialization:
        FIELDS = ["id", "name", "description", "aliases", "args"]


class ChannelCommand(SerializableModel):
    channel = models.ForeignKey(UserChannel, on_delete=models.CASCADE, related_name="commands")
    command = models.ForeignKey(Command, on_delete=models.CASCADE)
    is_enabled = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["channel", "command"], name="channel_command_unique")
        ]

    class Serialization:
        FIELDS = ["id", "is_enabled"]
