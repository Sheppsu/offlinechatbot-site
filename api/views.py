from django.http import JsonResponse

from main.models import Command


def success(data, status=200):
    return JsonResponse({"data": data}, status=status, safe=False)


def get_commands(req):
    return success([cmd.serialize() for cmd in Command.objects.all()])
