# Build Tool


## Context

We need to select a build tool for managing dependencies for, building, and distributing `dbt-common`.  While tooling can vary, this repo can serve as an OSS template for other OSS at dbt Labs and beyond.


## Options

- `setuptools` (`twine`, `build`)
- `hatch`
- `poetry`


### setuptools

#### Pro's

- most popular option
- supported by Python Packaging Authority
- build tool of record for dbt-core & existing internal adapters

#### Con's

- less flexible; forced to support backwards compatibility more so than other options
- no dependency management (manually add to `pyproject.toml`)


### hatch

#### Pro's

- supported by Python Packaging Authority
- already used by `dbt-semantic-layer` and `internal-actions`
- supports running tests against multiple versions of python locally (same functionality as `tox`)
- supports configuring workflows in `pyproject.toml` (same functionality as `make`)
- incorporates new PEP's quickly
- Manages python distributions itself without need of pyenv.  This allows Windows and non-Windows users to both work locally in the same way.
- used by black, tox, pipx, Jupyter Notebook, Datadog

#### Con's

- far less popular than other options
- no dependency management (manually add to `pyproject.toml`)
- only one maintainer (but is officially part of the larger PyPA working group)
- Hatch does not allow for the installation of specific patch release versions of itself but rather only uses minor release granularity that tracks the latest patch release


### poetry

#### Pro's

- second most popular option, similar in popularity to `setuptools`
- dependency management (`poetry add "my-dependency"`)
- provides a lock file
- more than one maintainer

#### Con's

- incorporates new PEP's slowly


## Decision

#### Selected: `hatch`

This option aligns with `dbt-adapter` and `dbt-semantic-layer`, which minimizes confusion
for anyone working in multiple repositories.
`hatch` also replaces `tox` and `make`, which consolidates our toolset to make working locally and with CI more consistant.


## Consequences

- [+] retire `tox`
- [+] retire `make`
- [+] rewriting the release workflows will create a more intuitive release for hatch projects
- [-] we cannot reuse the existing release workflows
- [-] write more detailed docs given lower familiarity
- [-] learning curve
