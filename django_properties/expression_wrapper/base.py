from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from django.db.models import Expression, F
    ExpressionType = Union[Expression, F]


class ExpressionWrapper:
    expression = None  # type: 'ExpressionType'

    def __init__(self, expression: 'ExpressionType'):
        self.expression = expression

    def as_python(self, obj: Any) -> Any:
        raise NotImplementedError
