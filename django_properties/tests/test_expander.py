import django
import pytest
from django.db import models
from django.db.models import Lookup, F, ExpressionWrapper, Value, Q
from django.db.models.functions import Lower
from django.db.models.lookups import Exact, GreaterThan

from django_properties.expander import expand_query


models.CharField.register_lookup(Lower)


skip_if_no_expression_comparison = pytest.mark.skipif(
    django.VERSION < (2,),
    reason="Django 2.0+ needed for Expression comparison",
)


class FakeModel(models.Model):
    char_field = models.CharField(max_length=150, default="")
    int_field = models.IntegerField(default=0)
    float_field = models.FloatField(default=0.)
    m2o_field = models.ForeignKey('self', on_delete=models.CASCADE, null=True)


def lookup_eq_lookup(lookup1: Lookup, lookup2: Lookup) -> bool:
    return bool(
        type(lookup1) == type(lookup2)
        and lookup1.lhs == lookup2.lhs
        and lookup1.rhs == lookup2.rhs
        and lookup1.bilateral_transforms == lookup2.bilateral_transforms
    )


@skip_if_no_expression_comparison
def test_lookup_comparison():
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


@skip_if_no_expression_comparison
@pytest.mark.django_db(transaction=True)
def test_char_expression():
    expected = Exact(Lower(
        ExpressionWrapper(F('char_field'), output_field=models.CharField())
    ), Value(''))
    query_1 = Q(char_field__lower='')
    query_2 = Q(char_field__lower__exact='')

    expanded_1 = expand_query(FakeModel, query_1)
    expanded_2 = expand_query(FakeModel, query_2)

    assert lookup_eq_lookup(expected, expanded_1)
    assert lookup_eq_lookup(expected, expanded_2)
