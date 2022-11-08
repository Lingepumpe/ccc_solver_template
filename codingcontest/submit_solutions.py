import os
import sys
from glob import glob
from pathlib import Path

import typer
from git import Repo
from loguru import logger

from codingcontest.catcoder import CatCoder
from codingcontest.next_level import commit, next_level


def submit_solutions_cli(
    check_all: bool = typer.Option(False, help="Force re-checking all stages"),  # noqa: B008
    verbose: bool = typer.Option(False, "--verbose", "-v"),  # noqa: B008
    only_for_stage: str = "",
    upload_solution_for_bonus: str = "solve.py",
) -> None:
    if not verbose:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
    submit_solutions(
        check_all=check_all,
        only_for_stage=only_for_stage,
        upload_solution_for_bonus=upload_solution_for_bonus,
    )


def submit_solutions(
    check_all: bool = False,
    only_for_stage: str = "",
    upload_solution_for_bonus: str = "solve.py",
    catcoder: CatCoder | None = None,
) -> None:
    root_dir = Path(__file__).parent
    if os.getenv("CCC_GIT_MODE") != "none":
        gitrepo = Repo(root_dir.parent)
        if gitrepo.bare:
            logger.error(f"Git repo in {root_dir.parent.absolute()} is a bare repo")
            raise typer.Exit(code=1)
    if catcoder is None:
        catcoder = CatCoder()
    catcoder_level_info = catcoder.current_level_info()
    output_files_path = root_dir / f"level{catcoder_level_info.level_nr}" / "out"
    if not output_files_path.exists():
        logger.warning(f"{output_files_path.absolute()} does not exist, maybe next-level? 🙃")
        raise typer.Exit(code=1)
    expected_stages = set(catcoder_level_info.input_names)
    if only_for_stage:
        existing_stages = {only_for_stage}
    else:
        existing_stages = {f"{Path(fstr).stem}" for fstr in glob(f"{output_files_path}/*.out")}
    previously_successful = set()
    if not check_all and (output_files_path / ".successfully_submitted").exists():
        with open(output_files_path / ".successfully_submitted", encoding="utf-8") as fin:
            previously_successful = {line.strip() for line in fin.readlines() if line.strip()}
    to_check = sorted((expected_stages & existing_stages) - previously_successful)
    logger.debug(f"Submission candidates: {', '.join(to_check)}")
    successful_stages = []
    did_fail = False
    for stage in to_check:
        if catcoder.upload_solution(
            output_files_path / f"{stage}.out", stage, catcoder_level_info.is_output_files
        ):
            logger.info(f"{stage} ✅")
            successful_stages.append(stage)
        else:
            logger.info(f"{stage} ❌")
            did_fail = True
    if expected_stages == previously_successful.union(successful_stages):
        if os.getenv("CCC_GIT_MODE") != "none":
            commit(
                gitrepo,
                f"level{catcoder_level_info.level_nr} done",
                add_path=output_files_path,
                add_updated=True,
            )
        if (solution_path := Path(output_files_path.parent) / upload_solution_for_bonus).exists():
            catcoder.upload_source(path=solution_path)
            logger.info(f"Solution {upload_solution_for_bonus} uploaded for bonus minutes]")
        else:
            logger.info("No solution uploaded for bonus minutes")

        if catcoder_level_info.level_nr == catcoder_level_info.max_level_nr:
            logger.info("🎉🥳 Congrats, all levels complete! 🥳🎉")
            raise typer.Exit()
        else:
            logger.info(f"🥳 Level {catcoder_level_info.level_nr} complete! 🎉\n")

            next_level(catcoder=catcoder)
    elif successful_stages:
        with open(output_files_path / ".successfully_submitted", "w", encoding="utf-8") as fout:
            fout.writelines(
                [f"{line}\n" for line in sorted(previously_successful) + successful_stages]
            )
        if os.getenv("CCC_GIT_MODE") != "none":
            commit(
                gitrepo,
                f"level{catcoder_level_info.level_nr} wip ({', '.join(successful_stages)} complete)",
                add_path=output_files_path,
                add_updated=True,
            )
    if did_fail:
        raise typer.Exit(-1)


def run() -> None:
    typer.run(submit_solutions_cli)


if __name__ == "__main__":
    run()
