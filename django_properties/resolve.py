from django.db.models.constants import LOOKUP_SEP


class Resolver:
    __slots__ = (
        'doc',
    )

    def __init__(self, doc):
        self.doc = doc

    def resolve(self, path):
        if LOOKUP_SEP in path:
            raise NotImplementedError("can't resolve through a lookup yet")
        return getattr(self.doc, path)
