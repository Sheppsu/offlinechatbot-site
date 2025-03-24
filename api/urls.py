from django.urls import path

from . import views

urlpatterns = [
    path("commands/", views.get_commands),
    path("commands/<int:id>/", views.toggle_command),

    path("channels/<int:id>/settings/", views.update_channel_setting),
    path("channels/create", views.create_channel),

    path("admin/add-connection/", views.admin_add_connection),
]
