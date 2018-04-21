from typing import TYPE_CHECKING, Any, Union, TypeVar, Tuple, Dict

from django.db.models.expressions import Col

from django_properties.utils import cached_property

if TYPE_CHECKING:
    from django.db.models import Expression, F, Q

    ExpressionType = Union[Expression, F]


Q_T = TypeVar('Q_T', bound='Q')


class FakeQuery:
    @classmethod
    def resolve_ref(cls, name: str, *_: Any, **__: Any) -> Col:
        # We need to do some faking of the ref resolution.
        # This essentially enables us to have a bit more complete
        # workings of F().
        return Col(name, None)

    @classmethod
    def _add_q(cls, node: Q_T, *_: Any, **__: Any) -> Tuple[Q_T, None]:
        return node, None

    @classmethod
    def promote_joins(cls, *_: Any, **__: Any) -> None:
        pass


class ExpressionWrapper:
    expression = None  # type: 'ExpressionType'

    def __init__(self, expression: 'ExpressionType') -> None:
        self.expression = expression

    def as_python(self, obj: Any) -> Any:
        raise NotImplementedError

    @cached_property
    def resolved_expression(self) -> 'ExpressionType':
        return self.expression.resolve_expression(FakeQuery)
