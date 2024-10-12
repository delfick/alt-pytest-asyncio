import pathlib

available_examples: list[str] = [
    p.name
    for p in (pathlib.Path(__file__).parent / "examples").iterdir()
    if p.is_dir() and p.name.startswith("example_")
]
