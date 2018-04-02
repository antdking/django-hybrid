from django.core.exceptions import FieldError
from django.db.models import Value, F

from django_properties.expression_wrapper.base import ExpressionWrapper
from django_properties.expression_wrapper.registry import register
from django_properties.resolve import Resolver


@register(Value)
class ValueWrapper(ExpressionWrapper):
    def as_python(self, obj):
        value = self.expression.value

        try:
            field = self.expression.field
        except FieldError:
            pass  # no output_field defined
        else:
            if field:
                # TODO: decide if it's better to use get_db_converters here
                value = field.to_python(value)
        return value


@register(F)
class FieldWrapper(ExpressionWrapper):
    def as_python(self, obj):
        resolver = Resolver(obj)
        return resolver.resolve(self.expression.name)
