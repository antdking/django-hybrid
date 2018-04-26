# Django Hybrid

Hybrid model properties for Django


### What is this?
Django Hybrid introduces a way to consolidate logic you run in the database,
and logic you run in your apps.

A common practice in Django is to use Database functions. You have probably done
something like this before:

```python
from django.db.models.functions import Concat
people = Person.objects.annotate(full_name=Concat('first_name', 'last_name'))
```

This is great if everything you're doing is in the database. However there are times
when you need to get the full name of someone who isn't in the database, or if
modifications are made to the data held in memory.

The aim of this project is to remove the duplicated code that will inevitably occur,
while providing a simple interface.


## Usage
Install using `pip`:
```bash
pip install django-hybrid
```

### `dj_hybrid.property` (or `hybrid_property`)
`hybrid_property` is a decorator that takes a class method, and returns a descriptor.

```python
import dj_hybrid
from django.db.models import Value as V
from django.db.models.functions import Concat

class Person:
    @dj_hybrid.property
    def full_name(cls):
        return Concat('first_name', V(' '), 'last_name')
```

This will output one of 2 things:

#### Class Property
as a class property, the output will be the original expression you have made.
Note that it will actually be thinly wrapped. This is to allow annotations to be
added without specifying the name.
```python
>>> Person.full_name
NamedExpression(Concat('first_name', V(' '), 'last_name'), name='full_name')
```

This can then be used in an annotation:
```python
Person.objects.create(first_name='Bob', last_name='Marley')
person = Person.objects.annotate(Person.full_name).get()
assert person.full_name == 'Bob Marley'
```
You can clear the result in the usual way, which will let you begin using the below method:
```python
del person.full_name  # clears 'full_name' from '__dict__'
```

#### Instance Property
as an instance property, the output will be the evaluated calculation.
```python
>>> Person(first_name="Bob", "Marley").full_name
'Bob Marley'
```


### Bugs?
If you find bugs, please report them into Github Issues.
\# TODO: introduce bug report templates

### Contributing
\# TODO
