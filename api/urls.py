from django.urls import path

from . import views

urlpatterns = [
    path("commands/", views.get_commands, name="api_commands"),
]
