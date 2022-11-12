import os
import shutil
import sys
from glob import glob
from pathlib import Path

import typer
from git import Repo
from loguru import logger

from codingcontest.catcoder import CatCoder


def commit(gitrepo: Repo, message: str, *, add_path: Path | None, add_updated=False):
    if add_path is not None:
        gitrepo.index.add(str(add_path))
    if add_updated:
        gitrepo.git.add(update=True)
    gitrepo.index.commit(message)
    if os.getenv("CCC_GIT_MODE") == "remote" and "origin" in gitrepo.remotes:
        gitrepo.remotes.origin.pull(rebase=True)
        gitrepo.remotes.origin.push()


def next_level_cli(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:  # noqa: B008
    if not verbose:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
    next_level()


def next_level(catcoder: CatCoder | None = None) -> None:
    root_dir = Path(__file__).parent
    if os.getenv("CCC_GIT_MODE") != "none":
        gitrepo = Repo(root_dir.parent)
        if gitrepo.bare:
            logger.error(f"Git repo in {root_dir.parent.absolute()} is a bare repo")
            raise typer.Exit(code=1)
        if gitrepo.is_dirty():
            logger.error(f"Git repo {root_dir.parent.absolute()} is dirty, commit your changes!")
            raise typer.Exit(code=1)

    max_level_present = max(
        (
            int(Path(lname).parts[-1][len("level") :])
            for lname in glob(f"{root_dir.absolute()}/level[0-9]")
            + glob(f"{root_dir.absolute()}/level[0-9][0-9]")
        ),
        default=None,
    )
    if max_level_present is not None:
        copy_from = root_dir / f"level{max_level_present}"
    else:
        copy_from = root_dir / "template"

    if not copy_from.exists() or not copy_from.is_dir():
        logger.error(f"{copy_from.absolute()} not a valid directory, cannot copy template files!")
        raise typer.Exit(code=1)

    if catcoder is None:
        catcoder = CatCoder()
    catcoder_level_info = catcoder.current_level_info()
    new_level_path = root_dir / f"level{catcoder_level_info.level_nr}"
    if new_level_path.exists():
        logger.warning(f"{new_level_path.absolute()} already exists, nothing to do.")
        raise typer.Exit(code=1)

    logger.debug(f"Copying {copy_from.absolute()} to {new_level_path.absolute()}")
    shutil.copytree(
        copy_from,
        new_level_path,
        ignore=lambda _, names: [
            n for n in names if n.endswith(".in") or n.endswith(".out") or n.endswith(".pdf")
        ],
    )
    archive_path = catcoder.download_level_files(
        new_level_path, catcoder_level_info.is_input_files
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
            catcoder_level_info.input_names, catcoder_level_info.input_file_names
        ):
            with open(new_level_path / "in" / f"{stage_name}.in", "w", encoding="utf-8") as fout:
                fout.write(f"{input_content}\n")

    logger.debug("Commiting level start")
    if os.getenv("CCC_GIT_MODE") != "none":
        commit(
            gitrepo, message=f"level{catcoder_level_info.level_nr} start", add_path=new_level_path
        )


def run() -> None:
    typer.run(next_level_cli)


if __name__ == "__main__":
    run()
