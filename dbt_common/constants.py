# Prefix which identifies environment variables which contains secrets.
SECRET_ENV_PREFIX = "DBT_ENV_SECRET"

# Prefix which identifies environment variables that should not be visible
# via macros, flags, or other user-facing mechanisms.
PRIVATE_ENV_PREFIX = "DBT_ENV_PRIVATE"

# Prefix for dbt engine environment varaibles that are user settable
ENGINE_ENV_PREFIX = "DBT_ENGINE"
