"""camas task definitions for bleak.

A drop-in, more expressive replacement for the ``[tool.poe.tasks]`` config in
``pyproject.toml``. The same definitions drive local development and CI.

    camas --list              # all tasks, one line each
    camas <task> --help       # a task's expanded tree + matrix axes
    camas --dry-run <task>    # preview the command tree without running it

poe -> camas command map:

    uv run poe lint                 ->  uv run camas lint
    uv run poe lint --checkonly     ->  uv run camas lint-check
    uv run poe typecheck            ->  uv run camas typecheck
    uv run poe test-all             ->  uv run camas test-all
    uv run poe test-py312           ->  uv run camas test-all --PY 3.12
    uv run poe test-py312 -- -k x   ->  uv run camas test -- -k x      (ambient)
    uv run poe docs                 ->  uv run camas docs

Extra pytest args that poe forwarded via ``$POE_EXTRA_ARGS`` are passed after a
``--`` separator, which camas appends to the leaf command:

    uv run camas test -- --cov-report=xml --junitxml=junit.xml -o junit_family=legacy
    uv run camas test -- --bleak-bluez-vhci
"""

from camas import Parallel, Sequential, Task

PYTHON_VERSIONS: tuple[str, ...] = ("3.10", "3.11", "3.12", "3.13", "3.14")


def _uv(
    *args: str,
    group: str,
    venv: str | None = None,
    python: str | None = None,
    with_pkg: str | None = None,
    help: str | None = None,
) -> Task:
    """A ``uv run`` invocation carrying only ``group`` (never ``dev``), optionally
    pinned to its own environment / interpreter / ephemeral package.

    This is the camas spelling of poe's
    ``executor = { no-group = "dev", group = group, python = python, with = with_pkg, isolated = true }``.
    ``venv`` (``UV_PROJECT_ENVIRONMENT``) keeps each tool out of the project's
    ``dev`` ``.venv`` — poe's ``isolated = true`` intent, but cached between runs.
    """
    return Task(
        (
            "uv", "run",
            "--no-group", "dev",
            "--group", group,
            *(("--python", python) if python is not None else ()),
            *(("--with", with_pkg) if with_pkg is not None else ()),
            *args,
        ),
        env={"UV_PROJECT_ENVIRONMENT": venv} if venv is not None else {},
        help=help,
    )


# --- format / lint (group = "lint", isolated in .venv-lint) -----------------

def _isort(*flags: str) -> Task:
    return _uv("isort", *flags, group="lint", venv=".venv-lint")


def _black(*flags: str) -> Task:
    return _uv("black", *flags, group="lint", venv=".venv-lint")


_flake8 = _uv(
    "flake8", ".", "--count", "--show-source", "--statistics",
    group="lint", venv=".venv-lint",
)

format = Sequential(
    _isort("."), _isort("docs"), _black("."),
    help="Apply isort + black (rewrites files)",
)

lint = Sequential(
    format, _flake8,
    help="Format with isort/black, then flake8 (poe `lint`)",
)

lint_check = Sequential(
    _isort(".", "--check", "--diff"),
    _isort("docs", "--check", "--diff"),
    _black(".", "--check", "--diff"),
    _flake8,
    help="Verify formatting + flake8, no writes (poe `lint --checkonly`)",
)


# --- typecheck (latest mypy + pyright, installed ephemerally) ---------------

# poe ran these as a fail-fast sequence; Parallel surfaces both tools at once.
mypy = _uv("mypy", group="test", venv=".venv-mypy", with_pkg="mypy")
pyright = _uv("pyright", group="test", venv=".venv-pyright", with_pkg="pyright")
typecheck = Parallel(mypy, pyright, help="mypy + pyright (latest), concurrently")


# --- test -------------------------------------------------------------------

_PYTEST: tuple[str, ...] = ("pytest", "tests", "-v")

# One leaf in an isolated env. Forward pytest args after `--` (poe's $POE_EXTRA_ARGS):
#   camas test -- --cov-report=xml --bleak-bluez-vhci
test = _uv(*_PYTEST, group="test", venv=".venv-test")

# Every supported interpreter, each in its own venv, all concurrent. One
# definition replaces poe's five `test-pyXXX` tables AND the `test-all` sequence.
#   camas test-all            # all versions
#   camas test-all --PY 3.12  # one cell (auto-generated matrix-axis flag)
test_all = Parallel(
    _uv(*_PYTEST, group="test"),
    matrix={"PY": PYTHON_VERSIONS},
    env={"UV_PROJECT_ENVIRONMENT": ".venv-{PY}", "UV_PYTHON": "{PY}"},
    help="Run the suite on every supported Python (parallel, isolated venvs)",
)


# --- docs (Sphinx, pinned to 3.11 like poe) ---------------------------------

docs = _uv(
    "sphinx-build", "-b", "html", "-W",
    "-d", "docs/_build/doctrees", "docs", "docs/_build/html",
    group="docs", venv=".venv-docs", python="3.11",
    help="Build the HTML documentation (warnings are errors)",
)


# --- aggregates -------------------------------------------------------------

check = Parallel(
    lint_check, typecheck, test,
    help="lint-check + typecheck + test on one interpreter (pre-push)",
)

# The whole pipeline locally, fail-fast: lint, typecheck, then the full matrix.
ci = Sequential(
    lint_check, typecheck, test_all,
    help="Full local CI: lint-check, typecheck, then every Python",
)
