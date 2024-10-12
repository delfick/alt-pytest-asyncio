import os
import pathlib
import shutil
import subprocess
import sys

import click

here = pathlib.Path(__file__).parent


def run(*args: str) -> None:
    bash = shutil.which("bash")
    if bash is None:
        raise Exception("Couldn't find bash on PATH")

    try:
        subprocess.run([bash, str(here / "uv"), "run", *args], check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


@click.group()
def cli() -> None:
    pass


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def format(args: list[str]) -> None:
    """
    Run ruff format and ruff check fixing I and UP rules
    """
    if not args:
        args = [".", *args]
    subprocess.run([sys.executable, "-m", "ruff", "format", *args], check=True)
    subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--fix", "--select", "I,UP", *args],
        check=True,
    )


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def lint(args: list[str]) -> None:
    """
    Run ruff check
    """
    os.execv(sys.executable, [sys.executable, "-m", "ruff", "check", *args])


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def types(args: list[str]) -> None:
    """
    Run mypy
    """
    locations: list[str] = [a for a in args if not a.startswith("-")]
    args = [a for a in args if a.startswith("-")]

    if not locations:
        locations.append(str((here / "..").resolve()))
    else:
        cwd = pathlib.Path.cwd()
        paths: list[pathlib.Path] = []
        for location in locations:
            from_current = cwd / location
            from_root = here.parent / location

            if from_current.exists():
                paths.append(from_current)
            elif from_root.exists():
                paths.append(from_root)
            else:
                raise ValueError(f"Couldn't find path for {location}")

        locations = [str(path) for path in paths]

    run("python", "-m", "mypy", *locations, *args)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def tests(args: list[str]) -> None:
    """
    Run pytest
    """
    run("python", "-m", "pytest", *args)


if __name__ == "__main__":
    cli()
