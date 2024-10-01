import yaml

from dbt_config.external_config import ExternalCatalogConfig

__EXAMPLE_VALID_CONFIG = """
catalogs: # list of objects
  - name: "titanic" # p0 name of the catalog
    type: iceberg # p0
    management: # Not P0, this governs how dbt manages the catalog integration
        enabled: True # p0
        create_if_not_exists: True # we will likely default this to false as it typically requires admin privileges
        alter_if_different: False
        refresh: "always" #oneOf: "never"|"on-run-start"
    configuration:
        table_format: "iceberg" # p0 delta/hudi etc
        namespace: "default"
        external_location: 'azfs://external-location-bucket-path/directory'
            
  - name: "elmers"
    type: glue
    management: # Not P0, this governs how dbt manages the catalog integration
        create_if_not_exists: True
        alter_if_different: False
        read_only: True # if we try to persist a model here dbt raises an exception
    configuration:
        namespace: "awsdatacatalog"
        external_location: 's3://external-location-bucket-path/directory'
        aws_account_id: "123456089"
        role_arn: "someRole"
        table_format: "iceberg"
"""


def test_parse_external_config():
    unparsed_config = yaml.safe_load(__EXAMPLE_VALID_CONFIG)
    ExternalCatalogConfig.model_validate(unparsed_config)
