# Generated by Django 4.1.7 on 2024-12-04 00:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0003_alter_userafk_user_alter_userchannel_user_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userosudata",
            name="is_verified",
        ),
        migrations.AddField(
            model_name="userosuconnection",
            name="is_verified",
            field=models.BooleanField(default=False),
        ),
    ]
