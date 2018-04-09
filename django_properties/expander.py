from django.db.models import Model, Q, FieldDoesNotExist, F, ExpressionWrapper, Value, Field
from typing import Type, Union, Any, Tuple

from django.db.models.constants import LOOKUP_SEP
from django.db.models.lookups import Exact
from django.db.models.options import Options


def expand_query(model: Type[Model], query: Q):
    """
    Expand query expressions into a more consumable form

    The basic structure of a query is essentially:
      <field>[_<field>]+[_<transform>]+_<lookup>.
    note: even when absent, the lookup is always there. it defaults to `_exact`.

    We want to convert it into a form that will allow offloading logic into our
    expression wrappers.
    example:
    >>> Q(date_field__year__gte=2017)
    becomes:
    >>> YearGte(YearExtract(F('date_field')), 2017)
    """

    first_child = query.children[0]
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


def expand_child(model: Type[Model], child: Tuple[str, Any]):
    arg, value = child

    if not isinstance(value, Value):
        value = Value(value)

    parts = arg.split(LOOKUP_SEP)
    opts = model._meta  # type: Options
    inner_opts = opts
    field = None
    pos = 0

    # we need to work out the full field path, which we will put in an F()
    for pos, part in enumerate(parts):
        if part == 'pk':
            part = inner_opts.pk.name
        try:
            field = inner_opts.get_field(part)  # type: Field
        except FieldDoesNotExist:
            break
        else:
            if field.is_relation:
                inner_opts = field.model._meta  # type: Options

    else:
        # we never broke out, which means everything resolved correctly.
        # bump pos by one so we get no remainder
        pos += 1
        # we didn't break out, so we only have a field.
        return Exact(ExpressionWrapper(F(arg), output_field=field), value)

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

    lookup_name = remainder[:-1]
    lookup_class = lookup_expression.get_lookup(lookup_name)
    if not lookup_class:
        transformer = lookup_expression.get_transformer(part)
        if not transformer:
            raise Exception("invalid transform or field access: {}".format(lookup_name))
        lookup_expression = expression = transformer(expression)
        lookup_name = 'exact'
        lookup_class = lookup_expression.get_lookup(lookup_name)

    # we'd rather use isnull instead of Eq(None)
    if value.value is None and lookup_name in ('exact', 'iexact'):
        return lookup_expression.get_lookup('isnull')(expression, True)
    return lookup_class(expression, value)


def get_connector(connector_name: Union[Q.AND, Q.OR]) -> Union[Type['And'], Type['Or']]:
    return {
        Q.AND: And,
        Q.OR: Or,
    }[connector_name]


# These are stubs!
class And:
    def __init__(self, lhs, rhs):
        self.lhs, self.rhs = lhs, rhs


class Not:
    def __init__(self, expression):
        self.expression = expression


class Or:
    def __init__(self, lhs, rhs):
        self.lhs, self.rhs = lhs, rhs
