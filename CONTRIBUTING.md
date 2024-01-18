# Contributing to `dbt-common`

`dbt-common` is a shared common utility that dbt-core and adapter implementations use


1. [About this document](#about-this-document)
2. [Getting the code](#getting-the-code)
3. [Setting up an environment](#setting-up-an-environment)
4. [Running in development](#running-dbt-common-in-development)
5. [Testing](#testing)
6. [Debugging](#debugging)
7. [Adding or modifying a changelog entry](#adding-or-modifying-a-changelog-entry)
8. [Submitting a Pull Request](#submitting-a-pull-request)

## About this document

There are many ways to contribute to the ongoing development of `dbt-common`, such as by participating in discussions and issues. We encourage you to first read our higher-level document: ["Expectations for Open Source Contributors"](https://docs.getdbt.com/docs/contributing/oss-expectations).

The rest of this document serves as a more granular guide for contributing code changes to `dbt-common` (this repository). It is not intended as a guide for using `dbt-common`, and some pieces assume a level of familiarity with Python development (`hatch`, `pip`, etc). Specific code snippets in this guide assume you are using macOS or Linux and are comfortable with the command line.

If you get stuck, we're happy to help! Drop us a line in the `#dbt-core-development` channel in the [dbt Community Slack](https://community.getdbt.com).

### Notes

- **CLA:** Please note that anyone contributing code to `dbt-common` must sign the [Contributor License Agreement](https://docs.getdbt.com/docs/contributor-license-agreements). If you are unable to sign the CLA, the `dbt-common` maintainers will unfortunately be unable to merge any of your Pull Requests. We welcome you to participate in discussions, open issues, and comment on existing ones.
- **Branches:** All pull requests from community contributors should target the `main` branch (default).
- **Releases**: TBD

## Getting the code

### Installing git

You will need `git` in order to download and modify the source code.

### External contributors

If you are not a member of the `dbt-labs` GitHub organization, you can contribute to `dbt-common` by forking the `dbt-common` repository. For a detailed overview on forking, check out the [GitHub docs on forking](https://help.github.com/en/articles/fork-a-repo). In short, you will need to:

1. Fork the `dbt-common` repository
2. Clone your fork locally
3. Check out a new branch for your proposed changes
4. Push changes to your fork
5. Open a pull request against `dbt-labs/dbt-common` from your forked repository

### dbt Labs contributors

If you are a member of the `dbt-labs` GitHub organization, you will have push access to the `dbt-common` repo. Rather than forking `dbt-common` to make your changes, just clone the repository, check out a new branch, and push directly to that branch.

## Setting up an environment

There are some tools that will be helpful to you in developing locally. While this is the list relevant for `dbt-common` development, many of these tools are used commonly across open-source python projects.

### Tools

These are the tools used in `dbt-common` development and testing:

- [`hatch`](https://hatch.pypa.io/latest/) for project management
- [`flake8`](https://flake8.pycqa.org/en/latest/) for code linting
- [`black`](https://github.com/psf/black) for code formatting
- [`mypy`](https://mypy.readthedocs.io/en/stable/) for static type checking
- [`pre-commit`](https://pre-commit.com) to easily run those checks
- [`changie`](https://changie.dev/) to create changelog entries, without merge conflicts

A deep understanding of these tools in not required to effectively contribute to `dbt-common`, but we recommend checking out the attached documentation if you're interested in learning more about each one.

## Running `dbt-common` in development

### Installation

Ensure you have the latest version of pip installed with `pip install --upgrade pip` as well as [hatch](https://hatch.pypa.io/latest/install/).

### Running `dbt-common`

This repository cannot be run on its own.

## Testing

Once you're able to manually test that your code change is working as expected, it's important to run existing automated tests, as well as adding some new ones. These tests will ensure that:
- Your code changes do not unexpectedly break other established functionality
- Your code changes can handle all known edge cases
- The functionality you're adding will _keep_ working in the future


### Initial setup

- [Install pre-commit](https://pre-commit.com/#usage)
- [Install hatch](https://hatch.pypa.io/1.7/install/#pip)

- Nothing needed to set up your environments.  hatch will create your environment as defined in the `pyproject.toml` when you run.

- set up pre-commit to use hatch: `hatch run setup-pre-commit`

### Hatch Commands

See the pyproject.toml for a complete list of custom commands.  See the h[atch docs](https://hatch.pypa.io/latest/cli/reference/) for a description of built in commands and flags.  These are the most useful custom commands to use while developing.

|Type|Command|Description|
|---|---|---|
|Utility|`hatch run proto`|regenerate protobuf definitions|
|Testing|`hatch run test:unit`|run all tests|
|Testing|`hatch shell test`|Drops you into a shell env set up for manual testing|
|Code Quality|`hatch run lint:all`|run black, flake8 and mypy checks|
|Code Quality|`hatch run lint:black`|run black|
|Code Quality|`hatch run lint:flake8`|run flake8|
|Code Quality|`hatch run lint:mypy`|run mypy|
|Testing|`hatch shell lint`|Drops you into a shell env set up for manualcode quality checks|
|Code Quality|`hatch fmt`|runs ruff on all code|

## Debugging

1. Try using a debugger, like `ipdb`. For pytest: `--pdb --pdbcls=IPython.terminal.debugger:pdb`
2. 

### Assorted development tips
* Append `# type: ignore` to the end of a line if you need to disable `mypy` on that line.
* Sometimes flake8 complains about lines that are actually fine, in which case you can put a comment on the line such as: # noqa or # noqa: ANNN, where ANNN is the error code that flake8 issues.

## Adding or modifying a CHANGELOG Entry

We use [changie](https://changie.dev) to generate `CHANGELOG` entries. **Note:** Do not edit the `CHANGELOG.md` directly. Your modifications will be lost.

Follow the steps to [install `changie`](https://changie.dev/guide/installation/) for your system.

Once changie is installed and your PR is created for a new feature, simply run the following command and changie will walk you through the process of creating a changelog entry:

```shell
changie new
```

Commit the file that's created and your changelog entry is complete!

If you are contributing to a feature already in progress, you will modify the changie yaml file in dbt/.changes/unreleased/ related to your change. If you need help finding this file, please ask within the discussion for the pull request!

You don't need to worry about which `dbt-common` version your change will go into. Just create the changelog entry with `changie`, and open your PR against the `main` branch. All merged changes will be included in the next minor version of `dbt-common`. The Core maintainers _may_ choose to "backport" specific changes in order to patch older minor versions. In that case, a maintainer will take care of that backport after merging your PR, before releasing the new version of `dbt-common`.

## Submitting a Pull Request

Code can be merged into the current development branch `main` by opening a pull request. A `dbt-common` maintainer will review your PR. They may suggest code revision for style or clarity, or request that you add unit or integration test(s). These are good things! We believe that, with a little bit of help, anyone can contribute high-quality code.

Automated tests run via GitHub Actions. If you're a first-time contributor, all tests (including code checks and unit tests) will require a maintainer to approve. Changes in the `dbt-common` repository trigger integration tests against Postgres. dbt Labs also provides CI environments in which to test changes to other adapters, triggered by PRs in those adapters' repositories, as well as periodic maintenance checks of each adapter in concert with the latest `dbt-common` code changes.

Once all tests are passing and your PR has been approved, a `dbt-common` maintainer will merge your changes into the active development branch. And that's it! Happy developing :tada:


## Troubleshooting Tips
Sometimes, the content license agreement auto-check bot doesn't find a user's entry in its roster. If you need to force a rerun, add `@cla-bot check` in a comment on the pull request.
