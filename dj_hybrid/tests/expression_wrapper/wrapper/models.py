from django.db import models


class WrapperStubModel(models.Model):
    pass


class FTestingModel(models.Model):
    int_field = models.IntegerField()
    str_field = models.CharField(max_length=150)
    related = models.ForeignKey('FTestingRelatedModel', on_delete=models.CASCADE, null=True)


class FTestingRelatedModel(models.Model):
    int_field = models.IntegerField()
    str_field = models.CharField(max_length=150)
