from django.urls import path

from . import views

urlpatterns = [
    path("", views.canvas, name="canvas"),
    path("leaderboard/", views.leaderboard, name="canvas_leaderboard")
]
