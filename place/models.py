from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class Placement(models.Model):
    timestamp = models.FloatField()
    user = models.ForeignKey(User, models.PROTECT, null=True)
    x = models.PositiveSmallIntegerField()
    y = models.PositiveSmallIntegerField()
    color = models.PositiveSmallIntegerField()
