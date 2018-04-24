import operator
from typing import Any, Callable, Tuple, Type, Union

from django.db.models import ExpressionWrapper, F, Field, FieldDoesNotExist, Model, Q, Value
from django.db.models.constants import LOOKUP_SEP
from django.db.models.lookups import Exact, Lookup
from django.db.models.options import Options
from django_properties.expression_wrapper.types import Wrapable

from .expression_wrapper.wrap import wrap

Connector_T = Union['Or', 'And']
LookupOrConnector_T = Union[Lookup, Connector_T]
Expanded_T = Union[LookupOrConnector_T, 'Not']


def expand_query(model: Type[Model], query: Q) -> Wrapable:
    """
    Expand query expressions into a more consumable form

    The basic structure of a query is essentially:
      <field>[_<field>]+[_<transform>]+_<lookup>.
    note: even when absent, the lookup is always there. it defaults to `_exact`.

    We want to convert it into a form that will allow offloading logic into our
    expression wrappers.

    We do not expect the output to be consumable within Django. This is only for
    our python bindings.

    example:
    >>> Q(date_field__year__gte=2017)
    becomes:
    >>> YearGte(YearExtract(F('date_field')), 2017)

    Some quirks to be aware of:
    When combining, we return some special classes; Not and And.

    When negating, a special Or class is returned.
    These will not function correctly as Django expressions.

    When an empty query is encountered, we return a special EmptyQuery object.
    This will always return True.
    It is also
    """

    try:
        first_child = query.children[0]
    except IndexError:
        expanded = EmptyQuery()
    else:
        if isinstance(first_child, Q):
            expanded = expand_query(model, first_child)
        else:
            expanded = expand_child(model, first_child)

    connector = get_connector(query.connector)

    for child in query.children[1:]:
        if isinstance(child, Q):
            expanded = connector(expanded, expand_query(model, child))
        else:
            expanded = connector(expanded, expand_child(model, child))

    if query.negated:
        expanded = Not(expanded)

    return expanded


def expand_child(model: Type[Model], child: Tuple[str, Any]) -> Lookup:
    arg, value = child

    if not isinstance(value, Value):
        value = Value(value)

    parts = arg.split(LOOKUP_SEP)
    opts = model._meta  # type: Options
    inner_opts = opts
    field = None  # type: Field
    pos = 0

    # we need to work out the full field path, which we will put in an F()
    for pos, part in enumerate(parts):
        if part == 'pk':
            part = inner_opts.pk.name
        try:
            field = inner_opts.get_field(part)
        except FieldDoesNotExist:
            break
        else:
            if field.is_relation:
                inner_opts = field.model._meta

    else:
        # we never broke out, which means everything resolved correctly.
        # bump pos by one so we get no remainder
        pos += 1

    if field is None:
        raise Exception("Field not found: {}".format(parts))

    field_path = LOOKUP_SEP.join(parts[:pos])
    expression = F(field_path)

    # we set lookup_expression to field as that's what we're gathering from.
    # It will be updated in parallel with `expression` later on
    lookup_expression = field
    # we need to wrap the F() so we can specify the output field.
    # It's kind of bastardised..
    expression = ExpressionWrapper(expression, output_field=field)

    remainder = parts[pos:]
    if not remainder:
        remainder = ['exact']

    # we don't try to access the last entry, as that is probably a lookup
    for part in remainder[:-1]:
        transformer = lookup_expression.get_transform(part)
        if not transformer:
            raise Exception("Invalid transform: {}".format(part))
        lookup_expression = expression = transformer(expression)

    lookup_name = remainder[-1]
    lookup_class = lookup_expression.get_lookup(lookup_name)
    if not lookup_class:
        transformer = lookup_expression.get_transform(lookup_name)
        if not transformer:
            raise Exception("invalid transform or field access: {}".format(lookup_name))
        lookup_expression = expression = transformer(expression)
        lookup_name = 'exact'
        lookup_class = lookup_expression.get_lookup(lookup_name)

    # we'd rather use isnull instead of Eq(None)
    if value.value is None and lookup_name in ('exact', 'iexact'):
        return lookup_expression.get_lookup('isnull')(expression, True)
    return lookup_class(expression, value)


def get_connector(connector_name: Union[Q.AND, Q.OR]) -> Callable[[Wrapable, Wrapable], Wrapable]:
    if connector_name == Q.AND:
        connector = And
    else:
        connector = Or

    def guard_empty(lhs: Wrapable, rhs: Wrapable) -> Wrapable:
        nonlocal connector
        if isinstance(lhs, EmptyQuery):
            return rhs
        if isinstance(rhs, EmptyQuery):
            return lhs
        # to reduce as much exposure to EmptyQuery as possible, remove it where we know it's
        # safe to remove. Django treats it as invisible, so should we.

        return connector(lhs, rhs)
    return guard_empty


class Combineable:
    combiner = None  # type: Callable[[bool, bool], bool]

    def __init__(self, lhs: Wrapable, rhs: Wrapable) -> None:
        self.lhs, self.rhs = lhs, rhs

    def as_python(self, obj: Any) -> bool:
        wrapped_lhs = wrap(self.lhs)
        wrapped_rhs = wrap(self.rhs)
        return type(self).combiner(wrapped_lhs.as_python(obj), wrapped_rhs.as_python(obj))


class And(Combineable):
    combiner = operator.and_


class Or(Combineable):
    combiner = operator.or_


class Not:
    def __init__(self, expression: Wrapable) -> None:
        self.expression = expression

    def as_python(self, obj: Any) -> bool:
        if isinstance(self.expression, EmptyQuery):
            # When an empty query is encountered, Django treats it as invisible.
            # This causes a strange behaviour of ~Q() behaving the same as Q().
            return True

        return not wrap(self.expression).as_python(obj)


class EmptyQuery:

    @staticmethod
    def as_python(obj: Any) -> bool:
        return True
