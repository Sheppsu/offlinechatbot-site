from django.urls import path

from . import views

urlpatterns = [
    path("commands/", views.get_commands, name="api_commands"),
    path("channels/<int:id>/settings/", views.update_channel_setting, name="api_update_channel_setting"),
]
