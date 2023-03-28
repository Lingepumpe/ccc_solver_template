import shutil
from glob import glob
from pathlib import Path

import typer
from loguru import logger

from codingcontest.catcoder import CatCoder
from codingcontest.utils import ROOT_DIR, commit, get_git_repo, set_logging


def next_level_cli(
    verbose: bool = typer.Option(False, "--verbose", "-v")  # noqa: FBT001, B008, FBT003
) -> None:
    set_logging(verbose=verbose)
    next_level()


def next_level(catcoder: CatCoder | None = None) -> None:
    gitrepo = get_git_repo(dirty_check=True)

    max_level_present = max(
        (
            int(Path(lname).parts[-1][len("level") :])
            for lname in glob(f"{ROOT_DIR.absolute()}/level[0-9]")
            + glob(f"{ROOT_DIR.absolute()}/level[0-9][0-9]")
        ),
        default=None,
    )
    if max_level_present is not None:
        copy_from = ROOT_DIR / f"level{max_level_present}"
    else:
        copy_from = ROOT_DIR / "template"

    if not copy_from.exists() or not copy_from.is_dir():
        logger.error(
            f"{copy_from.relative_to(ROOT_DIR)} not a valid directory, cannot copy template files!"
        )
        raise typer.Exit(code=1)

    if catcoder is None:
        catcoder = CatCoder()
    catcoder_level_info = catcoder.current_level_info()
    new_level_path = ROOT_DIR / f"level{catcoder_level_info.level_nr}"
    if new_level_path.exists():
        logger.warning(f"{new_level_path.relative_to(ROOT_DIR)} already exists, nothing to do.")
        raise typer.Exit(code=1)

    logger.debug(
        f"Copying {copy_from.relative_to(ROOT_DIR)} to {new_level_path.relative_to(ROOT_DIR)}"
    )
    shutil.copytree(
        copy_from,
        new_level_path,
        ignore=lambda _, names: [n for n in names if n.endswith((".in", ".out", ".pdf"))],
    )
    archive_path = catcoder.download_level_files(
        new_level_path, is_input_files=catcoder_level_info.is_input_files
    )
    (new_level_path / "in").mkdir(exist_ok=True)
    (new_level_path / "out").mkdir(exist_ok=True)
    (new_level_path / "out" / ".successfully_submitted").unlink(missing_ok=True)
    if archive_path is not None:
        shutil.unpack_archive(filename=archive_path, extract_dir=new_level_path / "in")
        archive_path.unlink()
        for actually_out_file in glob(f"{new_level_path.absolute()}/in/*.out"):
            shutil.move(actually_out_file, new_level_path / "out")
    else:  # We create fake "input files" from the text input
        for stage_name, input_content in zip(
            catcoder_level_info.input_names, catcoder_level_info.input_file_names, strict=True
        ):
            with (new_level_path / "in" / f"{stage_name}.in").open("w", encoding="utf-8") as fout:
                fout.write(f"{input_content}\n")

    logger.info(f"Created and filled '{new_level_path}'")
    commit(gitrepo, message=f"level{catcoder_level_info.level_nr} start", add_path=new_level_path)


def run() -> None:
    typer.run(next_level_cli)


if __name__ == "__main__":
    run()
