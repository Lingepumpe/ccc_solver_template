from dataclasses import dataclass
from glob import glob
from pathlib import Path

from loguru import logger

from codingcontest.catcoder import CatCoder
from codingcontest.submit_solutions import submit_solutions
from codingcontest.utils import set_logging


@dataclass
class Input:
    number_road_segments: int

    cars: list[str]

    input_file_stem: str

    @classmethod
    def from_file(cls: type["Input"], filename: str) -> "Input":
        cars = []
        with Path(filename).open(encoding="utf-8") as fin:
            number_road_segments = int(next(fin))
            number_cars = int(next(fin))
            for car_str in fin:
                cars.append(car_str)
            assert len(cars) == number_cars
        return Input(
            number_road_segments=number_road_segments,
            cars=cars,
            input_file_stem=Path(filename).stem,
        )


@dataclass
class Output:
    times: list[int]

    def write_file(self, output_stem: str) -> None:
        with (Path(__file__).parent / Path("out") / f"{output_stem}.out").open(
            "w", encoding="utf-8", newline="\r\n"
        ) as fout:
            fout.write(",".join([str(time) for time in self.times]) + "\n")


def solve(inclass: Input) -> bool:
    outclass = Output(times=[20 for c in inclass.cars])
    outclass.write_file(inclass.input_file_stem)
    return True


def main() -> None:
    considered_files = set(glob(f"{Path(__file__).parent}/in/*_example.in"))
    # considered_files = set(glob(f"{Path(__file__).parent}/in/*.in"))

    abort_on_first_fail = True

    set_logging(verbose=False)
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
