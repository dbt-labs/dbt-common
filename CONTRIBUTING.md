** replace `dbt-oss-template` with your repository name in all docs


# Contributing to `dbt-oss-template`

`dbt-oss-template` is a template for open source software projects at dbt Labs.


1. [About this document](#about-this-document)
2. [Getting the code](#getting-the-code)
3. [Setting up an environment](#setting-up-an-environment)
4. [Running in development](#running-dbt-oss-template-in-development)
5. [Testing](#testing)
6. [Debugging](#debugging)
7. [Adding or modifying a changelog entry](#adding-or-modifying-a-changelog-entry)
8. [Submitting a Pull Request](#submitting-a-pull-request)

## About this document

There are many ways to contribute to the ongoing development of `dbt-oss-template`, such as by participating in discussions and issues. We encourage you to first read our higher-level document: ["Expectations for Open Source Contributors"](https://docs.getdbt.com/docs/contributing/oss-expectations).

The rest of this document serves as a more granular guide for contributing code changes to `dbt-oss-template` (this repository). It is not intended as a guide for using `dbt-oss-template`, and some pieces assume a level of familiarity with Python development (virtualenvs, `pip`, etc). Specific code snippets in this guide assume you are using macOS or Linux and are comfortable with the command line.

If you get stuck, we're happy to help! Drop us a line in the `#dbt-oss-template-development` channel in the [dbt Community Slack](https://community.getdbt.com).

### Notes

- **CLA:** Please note that anyone contributing code to `dbt-oss-template` must sign the [Contributor License Agreement](https://docs.getdbt.com/docs/contributor-license-agreements). If you are unable to sign the CLA, the `dbt-oss-template` maintainers will unfortunately be unable to merge any of your Pull Requests. We welcome you to participate in discussions, open issues, and comment on existing ones.
- **Branches:** All pull requests from community contributors should target the `main` branch (default).
- **Releases**: This repository is never released.

## Getting the code

### Installing git

You will need `git` in order to download and modify the source code.

### External contributors

If you are not a member of the `dbt-labs` GitHub organization, you can contribute to `dbt-oss-template` by forking the `dbt-oss-template` repository. For a detailed overview on forking, check out the [GitHub docs on forking](https://help.github.com/en/articles/fork-a-repo). In short, you will need to:

1. Fork the `dbt-oss-template` repository
2. Clone your fork locally
3. Check out a new branch for your proposed changes
4. Push changes to your fork
5. Open a pull request against `dbt-labs/dbt-oss-template` from your forked repository

### dbt Labs contributors

If you are a member of the `dbt-labs` GitHub organization, you will have push access to the `dbt-oss-template` repo. Rather than forking `dbt-oss-template` to make your changes, just clone the repository, check out a new branch, and push directly to that branch.

## Setting up an environment

There are some tools that will be helpful to you in developing locally. While this is the list relevant for `dbt-oss-template` development, many of these tools are used commonly across open-source python projects.

### Tools

These are the tools used in `dbt-oss-template` development and testing:

- [`flake8`](https://flake8.pycqa.org/en/latest/) for code linting
- [`black`](https://github.com/psf/black) for code formatting
- [`mypy`](https://mypy.readthedocs.io/en/stable/) for static type checking
- [`pre-commit`](https://pre-commit.com) to easily run those checks
- [`changie`](https://changie.dev/) to create changelog entries, without merge conflicts

A deep understanding of these tools in not required to effectively contribute to `dbt-oss-template`, but we recommend checking out the attached documentation if you're interested in learning more about each one.

#### Virtual environments

We strongly recommend using virtual environments when developing code in `dbt-oss-template`. We recommend creating this virtualenv
in the root of the `dbt-oss-template` repository. To create a new virtualenv, run:
```sh
python3 -m venv env
source env/bin/activate
```

This will create and activate a new Python virtual environment.

## Running `dbt-oss-template` in development

### Installation

First make sure that you set up your `virtualenv` as described in [Setting up an environment](#setting-up-an-environment).  Also ensure you have the latest version of pip installed with `pip install --upgrade pip`. Next, install `dbt-oss-template` (and its dependencies):

```sh
git
pre-commit install
```

### Running `dbt-oss-template`

This repository is just a template and cannot be run.

## Testing

Once you're able to manually test that your code change is working as expected, it's important to run existing automated tests, as well as adding some new ones. These tests will ensure that:
- Your code changes do not unexpectedly break other established functionality
- Your code changes can handle all known edge cases
- The functionality you're adding will _keep_ working in the future


### Initial setup

None needed.

### Test commands

No tests included.


### Unit, Integration, Functional?

Here are some general rules for adding tests:
* unit tests (`tests/unit`) don’t need to access a database; "pure Python" tests should be written as unit tests
* functional tests (`tests/functional`) cover anything that interacts with a database, namely adapter

## Debugging

1. The logs for a `dbt run` have stack traces and other information for debugging errors (in `logs/dbt.log` in your project directory).
2. Try using a debugger, like `ipdb`. For pytest: `--pdb --pdbcls=IPython.terminal.debugger:pdb`
3. 

### Assorted development tips
* Append `# type: ignore` to the end of a line if you need to disable `mypy` on that line.
* Sometimes flake8 complains about lines that are actually fine, in which case you can put a comment on the line such as: # noqa or # noqa: ANNN, where ANNN is the error code that flake8 issues.
* To collect output for `CProfile`, run dbt with the `-r` option and the name of an output file, i.e. `dbt -r dbt.cprof run`. If you just want to profile parsing, you can do: `dbt -r dbt.cprof parse`. `pip` install `snakeviz` to view the output. Run `snakeviz dbt.cprof` and output will be rendered in a browser window.

## Adding or modifying a CHANGELOG Entry

We use [changie](https://changie.dev) to generate `CHANGELOG` entries. **Note:** Do not edit the `CHANGELOG.md` directly. Your modifications will be lost.

Follow the steps to [install `changie`](https://changie.dev/guide/installation/) for your system.

Once changie is installed and your PR is created for a new feature, simply run the following command and changie will walk you through the process of creating a changelog entry:

```shell
changie new
```

Commit the file that's created and your changelog entry is complete!

If you are contributing to a feature already in progress, you will modify the changie yaml file in dbt/.changes/unreleased/ related to your change. If you need help finding this file, please ask within the discussion for the pull request!

You don't need to worry about which `dbt-oss-template` version your change will go into. Just create the changelog entry with `changie`, and open your PR against the `main` branch. All merged changes will be included in the next minor version of `dbt-oss-template`. The Core maintainers _may_ choose to "backport" specific changes in order to patch older minor versions. In that case, a maintainer will take care of that backport after merging your PR, before releasing the new version of `dbt-oss-template`.

## Submitting a Pull Request

Code can be merged into the current development branch `main` by opening a pull request. A `dbt-oss-template` maintainer will review your PR. They may suggest code revision for style or clarity, or request that you add unit or integration test(s). These are good things! We believe that, with a little bit of help, anyone can contribute high-quality code.

Automated tests run via GitHub Actions. If you're a first-time contributor, all tests (including code checks and unit tests) will require a maintainer to approve. Changes in the `dbt-oss-template` repository trigger integration tests against Postgres. dbt Labs also provides CI environments in which to test changes to other adapters, triggered by PRs in those adapters' repositories, as well as periodic maintenance checks of each adapter in concert with the latest `dbt-oss-template` code changes.

Once all tests are passing and your PR has been approved, a `dbt-oss-template` maintainer will merge your changes into the active development branch. And that's it! Happy developing :tada:

Sometimes, the content license agreement auto-check bot doesn't find a user's entry in its roster. If you need to force a rerun, add `@cla-bot check` in a comment on the pull request.
