from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("token/", views.get_token, name="token"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("osuauth/", views.osu_auth),
    path("logininfo/", views.login_info, name="login_info")
]
