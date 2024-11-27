from django.db import models
from collections import defaultdict
from datetime import datetime


def enum_field(enum, field):
    def decorator(cls):
        return type(
            cls.__name__,
            (cls, field,),
            {
                "from_db_value": lambda self, value, expression, connection: enum(value) if value is not None else None,
                "to_python": lambda self, value: value if isinstance(value, enum) else enum(value),
                "get_prep_value": lambda self, value: value.value if isinstance(value, enum) else value
            }
        )
    return decorator


def _separate_field_args(fields, only_include_last=False):
    now = []
    later = defaultdict(list)
    for field in fields:
        split = field.split("__", 1)
        if len(split) > 1:
            later[split[0]].append(split[1])
        if not only_include_last or len(split) == 1:
            now.append(split[0])
    return now, later


class SerializableModel(models.Model):
    class Meta:
        abstract = True

    class Serialization:
        FIELDS: list
        EXCLUDES: list
        TRANSFORM: dict[str, str]

    def _transform(self, fields: list, excludes: dict, includes: dict):
        field_transforms = getattr(self.Serialization, "TRANSFORM", {})

        data = {}
        for field in fields:
            value = getattr(self, field)
            if isinstance(value, SerializableModel):
                value = value.serialize(includes.get(field), excludes.get(field))
            elif isinstance(value, datetime):
                value = value.isoformat()
            elif value.__class__.__name__ == "RelatedManager" or value.__class__.__name__ == "ManyRelatedManager":
                value = [obj.serialize(includes.get(field), excludes.get(field)) for obj in value.all()]

            data[field_transforms.get(field, field)] = value

        return data

    def serialize(self, includes: list | None = None, excludes: list | None = None):
        if includes is None:
            includes = []
        if excludes is None:
            excludes = []

        exclude_now, exclude_later = _separate_field_args(excludes, only_include_last=True)
        include_now, include_later = _separate_field_args(includes)

        fields = list(self.Serialization.FIELDS)
        for field in exclude_now:
            try:
                fields.remove(field)
            except ValueError:
                pass
        for field in include_now:
            fields.append(field)

        return self._transform(fields, exclude_later, include_later)
