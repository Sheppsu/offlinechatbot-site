from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard/", views.dashboard, name="dashboard"),

    path("token/", views.get_token, name="token"),
    path("login/", views.login),
    path("logout/", views.logout, name="logout"),
    path("osuauth/", views.osu_auth),
]
