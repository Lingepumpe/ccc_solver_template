import os
from glob import glob
from pathlib import Path
from typing import Optional

import typer
from git import Repo
from loguru import logger

from codingcontest.catcoder import CatCoder, LevelInfo
from codingcontest.next_level import next_level
from codingcontest.utils import ROOT_DIR, commit, get_git_repo, set_logging

StrOrNone = Optional[str]  # workaround typer not supporting "str | None"


def submit_solutions_cli(
    resubmit_successful: bool = typer.Option(  # noqa: B008, FBT001
        default=False, help="Force re-checking previously successful stages"
    ),
    continue_on_error: bool = typer.Option(  # noqa: B008, FBT001
        default=False, help="Do not stop on first unsuccessful stage"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),  # noqa: B008, FBT001, FBT003
    only_for_stage: str = typer.Option(  # noqa: B008
        default="", help="Check only specified stage, e.g. 'level_3_5'"
    ),
    upload_solution_for_bonus: StrOrNone = typer.Option(  # noqa: B008
        default=None,
        help="Specify filename from level folder for upload, otherwise we use from env",
    ),
) -> None:
    set_logging(verbose=verbose)
    submit_solutions(
        resubmit_successful=resubmit_successful,
        continue_on_error=continue_on_error,
        only_for_stage=only_for_stage,
        upload_solution_for_bonus=upload_solution_for_bonus,
    )


def submit_solutions(
    *,
    resubmit_successful: bool = False,
    continue_on_error: bool = False,
    only_for_stage: str = "",
    upload_solution_for_bonus: str | None = None,
    catcoder: CatCoder | None = None,
) -> None:
    gitrepo = get_git_repo(dirty_check=False)
    if catcoder is None:
        catcoder = CatCoder()

    catcoder_level_info = catcoder.current_level_info()
    output_files_path = ROOT_DIR / f"level{catcoder_level_info.level_nr}" / "out"
    if not output_files_path.exists():
        logger.warning(
            f"{output_files_path.relative_to(ROOT_DIR)} does not exist, maybe next-level? 🙃"
        )
        raise typer.Exit(code=1)
    to_check, required_for_completion = get_stages_to_check(
        catcoder_level_info=catcoder_level_info,
        only_for_stage=only_for_stage,
        output_files_path=output_files_path,
        resubmit_successful=resubmit_successful,
    )
    successful_stages = []
    did_fail = False
    for filestem, stage in to_check:
        if catcoder.upload_solution(
            output_files_path / f"{filestem}.out",
            stage,
            is_output_files=catcoder_level_info.is_output_files,
        ):
            logger.info(f"{filestem} success ✅")
            successful_stages.append(filestem)
        else:
            logger.info(f"{filestem} failed ❌")
            did_fail = True
            if not continue_on_error:
                break
    if required_for_completion == set(successful_stages):
        level_complete(
            gitrepo=gitrepo,
            catcoder_level_info=catcoder_level_info,
            output_files_path=output_files_path,
            upload_solution_for_bonus=upload_solution_for_bonus,
            catcoder=catcoder,
        )
        return

    if successful_stages:
        previously_successful = get_previously_successful(
            output_files_path=output_files_path,
            resubmit_successful=resubmit_successful,
        )
        with (output_files_path / ".successfully_submitted").open("w", encoding="utf-8") as fout:
            fout.writelines(
                [f"{line}\n" for line in sorted(list(previously_successful) + successful_stages)]
            )
        commit(
            gitrepo,
            f"level{catcoder_level_info.level_nr} wip ({', '.join(successful_stages)} complete)",
            add_path=output_files_path,
            add_updated=True,
        )
    if did_fail:
        raise typer.Exit(-1)


def get_stages_to_check(
    *,
    catcoder_level_info: LevelInfo,
    only_for_stage: str,
    output_files_path: Path,
    resubmit_successful: bool,
) -> tuple[list[tuple[str, str]], set[str]]:
    assert catcoder_level_info.input_names
    if len(catcoder_level_info.input_names[0]) <= len("99"):  # Indices, not file names
        existing_input_files = sorted(
            f"{Path(fstr).stem}" for fstr in glob(f"{output_files_path}/../in/*.in")
        )
        existing_input_files = [eip for eip in existing_input_files if "example" not in eip]
        assert len(existing_input_files) == len(
            catcoder_level_info.input_names
        ), f"{existing_input_files=} cannot be matched with {catcoder_level_info.input_names=}"
        expected_stages = dict(
            zip(existing_input_files, catcoder_level_info.input_names, strict=True)
        )
    else:
        expected_stages = {name: name for name in catcoder_level_info.input_names}
    if only_for_stage:
        existing_filestems = {only_for_stage}
    else:
        existing_filestems = {f"{Path(fstr).stem}" for fstr in glob(f"{output_files_path}/*.out")}
    if existing_filestems.isdisjoint(expected_stages) and not only_for_stage:
        logger.warning("No output files to check!")
    previously_successful = get_previously_successful(
        output_files_path, resubmit_successful=resubmit_successful
    )
    to_check = []
    for expected in sorted(expected_stages):
        if expected in existing_filestems:
            if expected in previously_successful and not resubmit_successful:
                logger.info(f"Previously successful {expected}, skipping")
            else:
                to_check.append((expected, expected_stages[expected]))

    logger.debug(f"Submission candidates: {to_check}")
    return to_check, expected_stages.keys() - previously_successful


def get_previously_successful(output_files_path: Path, *, resubmit_successful: bool) -> set[str]:
    if not resubmit_successful and (output_files_path / ".successfully_submitted").exists():
        with (output_files_path / ".successfully_submitted").open(encoding="utf-8") as fin:
            return {line.strip() for line in fin.readlines() if line.strip()}
    return set()


def upload_solution_for_bonus_minutes(
    solution_file: str | None, output_files_path: Path, catcoder: CatCoder
) -> None:
    """Upload solution_file from current level directory.

    If solution_file is not set, get filename from env
    """
    if solution_file is None:
        solution_file = os.getenv("CCC_SOLUTION_SUBMIT_FILE", None)
    if solution_file is None:
        logger.info("No solution uploaded for bonus minutes")
        return
    if (solution_path := Path(output_files_path.parent / solution_file)).exists():
        catcoder.upload_source(path=solution_path)
        logger.info(f"Solution {solution_file} uploaded for bonus minutes]")
    else:
        logger.warning(
            f"Could not find {solution_path.relative_to(ROOT_DIR)} for bonus minutes upload"
        )


def level_complete(
    gitrepo: Repo | None,
    catcoder_level_info: LevelInfo,
    output_files_path: Path,
    upload_solution_for_bonus: str | None,
    catcoder: CatCoder,
) -> None:
    """All steps necessary after a level has been completed."""
    commit(
        gitrepo,
        f"level{catcoder_level_info.level_nr} done",
        add_path=output_files_path,
        add_updated=True,
    )
    upload_solution_for_bonus_minutes(
        solution_file=upload_solution_for_bonus,
        output_files_path=output_files_path,
        catcoder=catcoder,
    )

    if catcoder_level_info.level_nr == catcoder_level_info.max_level_nr:
        logger.info("🎉🥳 Congrats, all levels complete! 🥳🎉")
        raise typer.Exit
    logger.info(f"🥳 Level {catcoder_level_info.level_nr} complete! 🎉\n")

    next_level(catcoder=catcoder)


def run() -> None:
    typer.run(submit_solutions_cli)


if __name__ == "__main__":
    run()
