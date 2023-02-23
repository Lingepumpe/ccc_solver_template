from dataclasses import dataclass
from glob import glob
from pathlib import Path
import sys

from loguru import logger

from codingcontest.catcoder import CatCoder
from codingcontest.submit_solutions import submit_solutions


@dataclass
class Input:
    max_power: int
    powers: list[int]

    input_file_stem: str

    @classmethod
    def from_file(cls: type["Input"], filename: str) -> "Input":
        powers = []
        with Path(filename).open(encoding="utf-8") as fin:
            max_power = int(next(fin))
            prices_count = int(next(fin))
            for _ in fin:
                powers.append(int(next(fin)))
            assert len(powers) == prices_count
        return Input(
            max_power=max_power,
            powers=powers,
            input_file_stem=Path(filename).stem,
        )


@dataclass
class Output:
    times: list[int]

    def write_file(self, output_stem: str) -> None:
        with (Path("out") / f"{output_stem}.out").open(
            "w", encoding="utf-8", newline="\r\n"
        ) as fout:
            fout.write(f"{len(self.times)}\n")
            for time in self.times:
                fout.write(f"{time}\n")


def solve(inclass: Input) -> bool:
    outclass = Output(times=[p for p in inclass.powers if p < 0])
    outclass.write_file(inclass.input_file_stem)
    return True


def main() -> None:
    considered_files = set(glob("in/*_example.in"))
    # considered_files = set(glob("in/*.in"))

    abort_on_first_fail = True

    logger.remove()
    logger.add(sys.stderr, level="INFO")
    previously_successful = set()
    if (Path("out") / ".successfully_submitted").exists():
        with (Path("out") / ".successfully_submitted").open(encoding="utf-8") as fin:
            previously_successful = {line.strip() for line in fin.readlines() if line.strip()}

    if len(previously_successful):
        logger.info(f"Skipping already submitted: {', '.join(sorted(previously_successful))}")
    considered_files = considered_files - previously_successful
    catcoder = CatCoder()

    for inputfile in sorted(considered_files):
        logger.info(f"Solving {Path(inputfile).stem}")
        inclass = Input.from_file(inputfile)
        if solve(inclass):
            try:
                submit_solutions(only_for_stage=Path(inputfile).stem, catcoder=catcoder)
            except Exception:  # noqa: BLE001
                if abort_on_first_fail:
                    return


if __name__ == "__main__":
    main()
