import dataclasses


# TODO: remove from dbt_common.contracts.util:: Replaceable + references
class Replaceable:
    def replace(self, **kwargs):
        return dataclasses.replace(self, **kwargs)


class Mergeable(Replaceable):
    def merged(self, *args):
        """Perform a shallow merge, where the last non-None write wins. This is
        intended to merge dataclasses that are a collection of optional values.
        """
        replacements = {}
        cls = type(self)
        for arg in args:
            for field in dataclasses.fields(cls):
                value = getattr(arg, field.name)
                if value is not None:
                    replacements[field.name] = value

        return self.replace(**replacements)
