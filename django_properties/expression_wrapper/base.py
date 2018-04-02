from typing import TYPE_CHECKING, Any, Union

from django.db.models.expressions import Col
from django.utils.functional import cached_property

if TYPE_CHECKING:
    from django.db.models import Expression, F
    ExpressionType = Union[Expression, F]


class FakeQuery:
    @classmethod
    def resolve_ref(cls, name, *args, **kwargs):
        # We need to do some faking of the ref resolution.
        # This essentially enables us to have a bit more complete
        # workings of F().
        return Col(name, None)


class ExpressionWrapper:
    expression = None  # type: 'ExpressionType'

    def __init__(self, expression: 'ExpressionType'):
        self.expression = expression

    def as_python(self, obj: Any) -> Any:
        raise NotImplementedError

    @cached_property
    def resolved_expression(self):
        return self.expression.resolve_expression(FakeQuery)
