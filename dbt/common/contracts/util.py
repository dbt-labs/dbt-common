import dataclasses


# TODO: remove from dbt.common.contracts.util:: Replaceable + references
class Replaceable:
    def replace(self, **kwargs):
        return dataclasses.replace(self, **kwargs)