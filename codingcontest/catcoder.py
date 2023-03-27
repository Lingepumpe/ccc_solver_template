from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import NamedTuple

from dotenv import load_dotenv
from loguru import logger
import requests

load_dotenv()


class LevelInfo(NamedTuple):
    level_nr: int
    max_level_nr: int
    is_contest_finished: bool
    input_names: tuple[str, ...]  # Names of the stages, e.g. level5_1
    input_file_names: tuple[
        str, ...
    ]  # Names of the input files, e.g. level5_1.in, or the input itself
    is_input_files: bool
    is_output_files: bool


@dataclass
class CatCoder:
    session: requests.Session = requests.Session()
    ccc_username: str = ""
    ccc_password: str = ""
    ccc_contest_id: str = ""

    def __post_init__(self) -> None:
        self.ccc_username = os.getenv("CCC_USERNAME", "")
        self.ccc_password = os.getenv("CCC_PASSWORD", "")
        self.ccc_contest_id = os.getenv("CCC_CONTEST_ID", "")
        assert self.ccc_username
        assert self.ccc_password
        assert self.ccc_contest_id
        self.login()

    def request(self, method: str, url: str, **kwargs: dict) -> requests.Response:
        logger.debug(f"{method}: {url}")
        try:
            res = self.session.request(method, url, **kwargs)  # type: ignore[arg-type]
        except (requests.RequestException, requests.ConnectionError) as e:
            logger.warning(f"Got an exception during {method} {url}: {e}")
            res = requests.Response()
            res.status_code = 500
            return res
        if res.status_code != 200:
            logger.warning(f"Received status_code {res.status_code} from {method} {url}")
            raise Exception(f"Received status_code {res.status_code} from {method} {url}")
        return res

    def login(self) -> None:
        self.session = requests.Session()

        # get xsrf/csrf token (is set as cookie). Works without?
        # xsrf_page_url = "https://catcoder.codingcontest.org/"
        # self.request(method="GET", url=xsrf_page_url)
        # logger.debug(f"Received XSRF-Token {self.session.cookies['XSRF-TOKEN']}")

        # get initial SESSION cookie
        session_url = (
            "https://catcoder.codingcontest.org/oauth2/authorization/"
            "cc-registration?referer=https://catcoder.codingcontest.org/"
        )
        self.request(method="GET", url=session_url)
        first_session = self.session.cookies["SESSION"]
        logger.debug(f"Received first SESSION cookie {first_session}")

        # get actual SESSION cookie
        payload = {
            "username": self.ccc_username,
            "password": self.ccc_password,
        }
        login_url = "https://register.codingcontest.org/auth/login"
        self.request(method="POST", url=login_url, data=payload)
        second_session = self.session.cookies["SESSION"]
        if first_session == second_session:
            logger.error(
                f"Failed login for {self.ccc_username}. Check your .env file (CCC_USERNAME + CCC_PASSWORD)"
            )
            raise Exception("Login Failed")
        logger.debug(f"Received second SESSION cookie {second_session}")

    def current_level_info(self) -> LevelInfo:
        res = self.request(
            method="GET",
            url=f"https://catcoder.codingcontest.org/api/game/input/info/{self.ccc_contest_id}",
        ).json()
        res2 = self.request(
            method="GET",
            url=f"https://catcoder.codingcontest.org/api/game/level/{self.ccc_contest_id}",
        ).json()
        is_input_files = res["hasInputFile"]
        if is_input_files:
            input_names = tuple(str(test["inputsDto"][0]["name"]) for test in res["tests"])
        else:
            input_names = tuple(str(idx) for idx in range(1, len(res["tests"]) + 1))
        return LevelInfo(
            level_nr=res["level"],
            max_level_nr=res2["nrOfLevels"],
            is_contest_finished=res2["gameFinished"],
            input_names=input_names,
            input_file_names=tuple(str(test["inputsDto"][0]["input"]) for test in res["tests"]),
            is_input_files=is_input_files,
            is_output_files=res["fileSolution"],
        )

    def download_level_files(self, path: Path, is_input_files: bool) -> Path | None:
        filetypes = ["description"]
        if is_input_files:
            filetypes.append("input")
        for filetype in filetypes:
            res = self.request(
                method="GET",
                url=f"https://catcoder.codingcontest.org/api/contest/{self.ccc_contest_id}/file-request/{filetype}",
            ).json()
            url = res["url"]
            res = requests.get(url)
            if "content-disposition" in res.headers:
                cd_header = res.headers["content-disposition"]
                filepath = path / re.findall(r'filename="(.+)"', cd_header)[0]
            else:
                filepath = path / url.split("/")[-1]
            with filepath.open("wb") as fout:
                fout.write(res.content)
        return filepath if is_input_files else None

    def upload_solution(self, path: Path, stage_name: str, is_output_files: bool) -> bool:
        if is_output_files:
            with path.open("rb") as fin:
                files = [("file", (path.parts[-1], fin, "text/plain"))]
                res = self.request(
                    method="POST",
                    url=f"https://catcoder.codingcontest.org/api/game/{self.ccc_contest_id}/upload/solution/{stage_name}",
                    files=files,  # type: ignore[arg-type]
                ).json()
        else:
            with path.open(encoding="utf-8") as fin:
                solution = next(fin).strip()  # consider only first line
                logger.debug(f"Submitting '{solution}' for stage {stage_name}")
                res = self.request(
                    method="POST",
                    url=f"https://catcoder.codingcontest.org/api/game/{self.ccc_contest_id}/submit",
                    json={"results": {stage_name: solution}},
                ).json()
        assert res["results"][stage_name] in {"VALID", "INVALID"}
        return res["results"][stage_name] == "VALID"

    def upload_source(self, path: Path) -> None:
        with path.open("rb") as fin:
            files = [("file", (path.parts[-1], fin, "text/plain"))]
            self.request(
                method="POST",
                url=f"https://catcoder.codingcontest.org/api/game/{self.ccc_contest_id}/1/upload",
                files=files,  # type: ignore
            )
