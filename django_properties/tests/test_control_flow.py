import pytest
from django.db import models
from django.db.models import Q, Case, When, Value

from django_properties.expression_wrapper import wrap


class ControlFlowModel(models.Model):
    char_field = models.CharField(max_length=150, default="")
    int_field = models.IntegerField(default=0)
    float_field = models.FloatField(default=0.)
    m2o_field = models.ForeignKey('self', on_delete=models.CASCADE, null=True)


@pytest.mark.django_db(transaction=True)
def test_query():
    expected = True
    query = Q(int_field__gt=20)
    wrapped = wrap(query)
    instance = ControlFlowModel(int_field=50)

    assert expected == wrapped.as_python(instance)


@pytest.mark.django_db(transaction=True)
def test_case():
    expected = "Woot!"
    expression = Case(
        When(int_field__lt=20, then=Value("got 20!")),
        When(int_field=23, then=Value("Woot!")),
    )
    wrapped = wrap(expression)
    instance = ControlFlowModel(int_field=23)

    assert expected == wrapped.as_python(instance)

