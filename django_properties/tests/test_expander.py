from functools import singledispatch

import django
import pytest
from django.db import models
from django.db.models import ExpressionWrapper, F, Lookup, Q, Value, IntegerField
from django.db.models.functions import Lower
from django.db.models.lookups import Exact, GreaterThan

from django_properties.expander import expand_query, Not, Combineable, And, EmptyQuery
from django_properties.expression_wrapper.wrap import wrap

models.CharField.register_lookup(Lower)

pytestmark = pytest.mark.django_db(transaction=True)
skip_if_no_expression_comparison = pytest.mark.skipif(
    django.VERSION < (2,),
    reason="Django 2.0+ needed for Expression comparison",
)


class FakeModel(models.Model):  # type: ignore
    char_field = models.CharField(max_length=150, default="")
    int_field = models.IntegerField(default=0)
    float_field = models.FloatField(default=0.)
    m2o_field = models.ForeignKey('self', on_delete=models.CASCADE, null=True)


@singledispatch
def lookup_eq_lookup(lookup1: Lookup, lookup2: Lookup) -> bool:
    return bool(
        type(lookup1) == type(lookup2)
        and lookup1.lhs == lookup2.lhs
        and lookup1.rhs == lookup2.rhs
        and lookup1.bilateral_transforms == lookup2.bilateral_transforms
    )


@lookup_eq_lookup.register(Not)
def _(lookup1: Not, lookup2: Not) -> bool:
    return bool(
        type(lookup1) == type(lookup2)
        and lookup_eq_lookup(lookup1.expression, lookup2.expression)
    )


@lookup_eq_lookup.register(Combineable)
def _(lookup1: Combineable, lookup2: Combineable) -> bool:
    return bool(
        type(lookup1) == type(lookup2)
        and lookup_eq_lookup(lookup1.lhs, lookup2.lhs)
        and lookup_eq_lookup(lookup1.rhs, lookup2.rhs)
    )


@lookup_eq_lookup.register(EmptyQuery)
def _(lookup1: EmptyQuery, lookup2: EmptyQuery) -> bool:
    return bool(
        type(lookup1) == type(lookup2)
    )


@skip_if_no_expression_comparison  # type: ignore
def test_lookup_comparison() -> None:
    q1 = Exact(Lower(
        ExpressionWrapper(F('char_field'), output_field=models.CharField())
    ), Value(''))
    q2 = Exact(Lower(
        ExpressionWrapper(F('char_field'), output_field=models.CharField())
    ), Value(''))
    q3 = GreaterThan(
        ExpressionWrapper(F('int_field'), output_field=models.IntegerField()),
        Value(2)
    )
    q4 = Exact(Lower(
        ExpressionWrapper(F('char_field'), output_field=models.TextField())
    ), Value(''))

    assert lookup_eq_lookup(q1, q2)
    assert not lookup_eq_lookup(q1, q3)
    assert not lookup_eq_lookup(q1, q4)


@skip_if_no_expression_comparison  # type: ignore
def test_char_expression() -> None:
    expected = Exact(Lower(
        ExpressionWrapper(F('char_field'), output_field=models.CharField())
    ), Value(''))
    query_1 = Q(char_field__lower='')
    query_2 = Q(char_field__lower__exact='')

    expanded_1 = expand_query(FakeModel, query_1)
    expanded_2 = expand_query(FakeModel, query_2)

    assert lookup_eq_lookup(expected, expanded_1)
    assert lookup_eq_lookup(expected, expanded_2)


@skip_if_no_expression_comparison
def test_nested_query():
    expected = Exact(
        ExpressionWrapper(F('char_field'), output_field=models.CharField()),
        Value(''))
    query = Q(Q(char_field=''))
    expanded = expand_query(FakeModel, query)
    assert lookup_eq_lookup(expected, expanded)


@skip_if_no_expression_comparison
def test_negated_query():
    expected = Not(Exact(
        ExpressionWrapper(F('char_field'), output_field=models.CharField()),
        Value('')
    ))
    query_1 = ~Q(char_field='')
    query_2 = Q(~Q(char_field=''))
    expanded_1 = expand_query(FakeModel, query_1)
    expanded_2 = expand_query(FakeModel, query_2)
    assert lookup_eq_lookup(expected, expanded_1)
    assert lookup_eq_lookup(expected, expanded_2)


@skip_if_no_expression_comparison
def test_and_query():
    expected = And(
        Exact(ExpressionWrapper(F('char_field'), output_field=models.CharField()), Value('')),
        Exact(ExpressionWrapper(F('int_field'), output_field=models.IntegerField()), Value(1)),
    )
    queries = [
        Q(char_field='', int_field=1),
        Q(Q(char_field=''), int_field=1),
        Q(Q(char_field=''), Q(int_field=1)),
        Q(char_field='') & Q(int_field=1),
    ]
    for query in queries:
        expanded = expand_query(FakeModel, query)
        assert lookup_eq_lookup(expected, expanded)


@skip_if_no_expression_comparison
def test_empty_query():
    expected = EmptyQuery()
    query = Q()
    expanded = expand_query(FakeModel, query)
    assert lookup_eq_lookup(expected, expanded)
    assert wrap(expanded).as_python(None)


@skip_if_no_expression_comparison
def test_negated_empty_query():
    expected = EmptyQuery()
    query = ~Q()
    expanded = expand_query(FakeModel, query)
    assert lookup_eq_lookup(expected, expanded)
    assert wrap(expanded).as_python(None)


@skip_if_no_expression_comparison
def test_combining_empty_query():
    # when Django combines an empty with an empty, it will only output one.
    expected = EmptyQuery()
    query = Q() & Q()
    expanded = expand_query(FakeModel, query)
    assert lookup_eq_lookup(expected, expanded)
    assert wrap(expanded).as_python(None)


@skip_if_no_expression_comparison
def test_combining_empty_with_query():
    expected = Exact(ExpressionWrapper(F('int_field'), output_field=IntegerField()), Value(1))
    query = Q() & Q(int_field=1)
    expanded = expand_query(FakeModel, query)
    assert lookup_eq_lookup(expected, expanded)
    assert wrap(expanded).as_python(dict(int_field=1))


@skip_if_no_expression_comparison
def test_multiple_empty_children():
    expected = EmptyQuery()
    query = Q(Q(), Q())
    expanded = expand_query(FakeModel, query)
    assert lookup_eq_lookup(expected, expanded)
    assert wrap(expanded).as_python(None)


@skip_if_no_expression_comparison
def test_adding_empty_as_a_child():
    expected = Exact(ExpressionWrapper(F('int_field'), output_field=IntegerField()), Value(1))
    query = Q(Q(), Q(int_field=1))
    expanded = expand_query(FakeModel, query)
    assert lookup_eq_lookup(expected, expanded)
    assert wrap(expanded).as_python(dict(int_field=1))


@skip_if_no_expression_comparison
def test_empty_in_empty():
    expected = EmptyQuery()
    query = Q(Q(Q(Q())))
    expanded = expand_query(FakeModel, query)
    assert lookup_eq_lookup(expected, expanded)
    assert expanded.as_python(None)


@skip_if_no_expression_comparison
def test_negated_empty_as_a_sibling():
    expected = Exact(ExpressionWrapper(F('int_field'), output_field=IntegerField()), Value(1))
    query = Q(~Q(), Q(int_field=1))
    expanded = expand_query(FakeModel, query)
    assert lookup_eq_lookup(expected, expanded)
    assert wrap(expanded).as_python(dict(int_field=1))
