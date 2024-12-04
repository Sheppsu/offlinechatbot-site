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
            user = User(
                id=twitch_user["id"],
                username=twitch_user["login"],
                permissions=permissions
            )
        user.save()
        return user

    def create_superuser(self, code):
        return self.create_user(code, UserPermissions.ADMIN)


class User(models.Model):
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

    def __str__(self):
        return self.username


class UserChannel(models.Model):
    user = models.OneToOneField("User", on_delete=models.CASCADE)
    is_offline_only = models.BooleanField()


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

    global_rank = models.PositiveIntegerField()


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


class Command(models.Model):
    name = models.CharField(max_length=32)
    description = models.CharField(max_length=1024)
    aliases = models.JSONField(default=list)
    args = models.JSONField(default=list)


class ChannelCommand(models.Model):
    channel = models.ForeignKey(UserChannel, on_delete=models.CASCADE, related_name="commands")
    command = models.ForeignKey(Command, on_delete=models.CASCADE)
    is_enabled = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["channel", "command"], name="channel_command_unique")
        ]
