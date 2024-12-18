## dbt-common

The shared common utilities for dbt-core and adapter implementations use

### Releasing dbt-common
To release a new version of dbt-common to pypi, you'll need to: 
1. Run the [release workflow](https://github.com/dbt-labs/dbt-common/actions/workflows/release.yml) to bump the version, generate changelogs and release to pypi
4. Bump the version of `dbt-common` in `dbt-core` and `dbt-adapters` if you're releasing a new major version or a pre-release: 
   * `dbt-core`: [setup.py](https://github.com/dbt-labs/dbt-core/blob/main/core/setup.py)
   * `dbt-adapters`: [pyproject.toml](https://github.com/dbt-labs/dbt-adapters/blob/main/pyproject.toml)
   * Adapter Implementations: 
     * `dbt-postgres`: [pyproject.toml](https://github.com/dbt-labs/dbt-postgres/blob/main/pyproject.toml)
     * `dbt-snowflake`: [setup.py](https://github.com/dbt-labs/dbt-snowflake/blob/main/setup.py)
     * `dbt-bigquery`: [setup.py](https://github.com/dbt-labs/dbt-bigquery/blob/main/setup.py)
     * `dbt-redshift`: [setup.py](https://github.com/dbt-labs/dbt-redshift/blob/main/setup.py)
     * `dbt-spark`: [setup.py](https://github.com/dbt-labs/dbt-spark/blob/main/setup.py)

## Getting started

- [Install dbt](https://docs.getdbt.com/docs/get-started/installation)
- Read the [introduction](https://docs.getdbt.com/docs/introduction/) and [viewpoint](https://docs.getdbt.com/docs/about/viewpoint/)

## Join the dbt Community

- Be part of the conversation in the [dbt Community Slack](http://community.getdbt.com/)
- Read more on the [dbt Community Discourse](https://discourse.getdbt.com)

## Reporting bugs and contributing code

- Want to report a bug or request a feature? Let us know and open [an issue](https://github.com/dbt-labs/dbt-common/issues/new/choose)
- Want to help us build dbt? Check out the [Contributing Guide](https://github.com/dbt-labs/dbt-common/blob/HEAD/CONTRIBUTING.md)

## Code of Conduct

Everyone interacting in the dbt project's codebases, issue trackers, chat rooms, and mailing lists is expected to follow the [dbt Code of Conduct](https://community.getdbt.com/code-of-conduct).
