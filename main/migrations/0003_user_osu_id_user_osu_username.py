# Generated by Django 4.2.2 on 2023-08-24 02:06

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0002_alter_user_last_placement"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="osu_id",
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="osu_username",
            field=models.CharField(max_length=45, null=True),
        ),
    ]
