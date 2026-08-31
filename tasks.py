"""camas tasks for bleak. Run ``camas --list`` or ``camas <task> --help``."""

from camas import Parallel, Sequential, Task

PYTHON_VERSIONS = ("3.10", "3.11", "3.12", "3.13", "3.14")

LINT = {"UV_PROJECT_ENVIRONMENT": ".venv-lint"}
TEST = {"UV_PROJECT_ENVIRONMENT": ".venv-test"}

PYTEST = "uv run --no-group dev --group test pytest tests -v"

lint_check = Parallel(
    Task("uv run --no-group dev --group lint isort . --check --diff"),
    Task("uv run --no-group dev --group lint isort docs --check --diff"),
    Task("uv run --no-group dev --group lint black . --check --diff"),
    Task(
        "uv run --no-group dev --group lint flake8 . --count --show-source --statistics"
    ),
    env=LINT,
)

format = Sequential(
    Parallel(
        Task("uv run --no-group dev --group lint isort ."),
        Task("uv run --no-group dev --group lint isort docs"),
    ),
    Task("uv run --no-group dev --group lint black ."),
    env=LINT,
)

typecheck = Parallel(
    Task("uv run --no-group dev --group test --with mypy mypy"),
    Task("uv run --no-group dev --group test --with pyright pyright"),
    env=TEST,
)

test = Task(PYTEST, env=TEST)

test_all = Parallel(
    Task(PYTEST),
    matrix={"PY": PYTHON_VERSIONS},
    env={"UV_PROJECT_ENVIRONMENT": ".venv-{PY}", "UV_PYTHON": "{PY}"},
)

docs = Task(
    "uv run --python 3.11 --no-group dev --group docs "
    "sphinx-build -b html -W -d docs/_build/doctrees docs docs/_build/html",
    env={"UV_PROJECT_ENVIRONMENT": ".venv-docs"},
)

check = Parallel(lint_check, typecheck, test)
ci = Parallel(lint_check, typecheck, test_all)
