from factory import RelatedFactory, SubFactory
from factory.django import DjangoModelFactory
from faker import Faker

from .models import WrapperStubModel, FTestingModel, FTestingRelatedModel

fake = Faker()


class WrapperStubFactory(DjangoModelFactory):
    class Meta:
        model = WrapperStubModel


class FTestingRelatedFactory(DjangoModelFactory):
    class Meta:
        model = FTestingRelatedModel

    int_field = fake.pyint()
    str_field = fake.pystr(max_chars=FTestingRelatedModel._meta.get_field('str_field').max_length)
    parent = RelatedFactory('dj_hybrid.tests.expression_wrapper.wrapper.factory.FTestingFactory', 'related')


class FTestingFactory(DjangoModelFactory):
    class Meta:
        model = FTestingModel

    int_field = fake.pyint()
    str_field = fake.pystr(max_chars=FTestingModel._meta.get_field('str_field').max_length)
    related = SubFactory(FTestingRelatedFactory, parent=None)
