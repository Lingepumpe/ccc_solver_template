import os
import sys
from pathlib import Path

import typer
from git import Repo
from loguru import logger

ROOT_DIR = Path(__file__).parent


def set_logging(*, verbose: bool = False) -> None:
    if not verbose:
        logger.remove()
        logger.add(sys.stderr, level="INFO")


def commit(
    gitrepo: Repo | None, message: str, *, add_path: Path | None, add_updated: bool = False
) -> None:
    """Commit changes if gitrepo is set."""
    if gitrepo is None:
        return
    if add_path is not None:
        gitrepo.index.add(str(add_path))
    if add_updated:
        gitrepo.git.add(update=True)
    gitrepo.index.commit(message)
    if os.getenv("CCC_GIT_MODE") == "remote" and "origin" in gitrepo.remotes:
        gitrepo.remotes.origin.pull(rebase=True)
        gitrepo.remotes.origin.push()


def get_git_repo(*, dirty_check: bool) -> Repo | None:
    """Check to see if git mode is enabled, return Repo if it is.

    Also check to see if repo is not a bare repo and not dirty
    """
    if os.getenv("CCC_GIT_MODE") == "none":
        return None
    gitrepo = Repo(ROOT_DIR.parent)
    if gitrepo.bare:
        logger.error(f"Git repo in {ROOT_DIR.parent.absolute()} is a bare repo")
        raise typer.Exit(code=1)
    if dirty_check and gitrepo.is_dirty():
        logger.error(f"Git repo {ROOT_DIR.parent.absolute()} is dirty, commit your changes!")
        raise typer.Exit(code=1)
    return gitrepo
