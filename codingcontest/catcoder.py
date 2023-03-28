import os
import re
from dataclasses import dataclass
from http import HTTPStatus
from io import BufferedReader
from pathlib import Path
from typing import Any, NamedTuple

import requests
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


class LevelInfo(NamedTuple):
    level_nr: int
    max_level_nr: int
    is_contest_finished: bool
    input_names: tuple[str, ...]  # Names of the stages, e.g. level5_1
    input_file_names: tuple[
        str, ...
    ]  # Names of the input files, e.g. level5_1.in, or the input itself
    is_input_files: bool  # files or text fields for input?
    is_output_files: bool  # files or text fields for output?


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
        self.contest_domain = os.getenv("CCC_CONTEST_DOMAIN", "codingcontest.org")
        assert self.ccc_username
        assert self.ccc_password
        assert self.ccc_contest_id
        self.login()

    def request(  # noqa: PLR0913
        self,
        method: str,
        url: str,
        data: dict[str, str] | None = None,
        files: list[tuple[str, tuple[str, BufferedReader, str]]] | None = None,
        json: dict[str, Any] | None = None,
    ) -> requests.Response:
        logger.debug(f"{method}: {url}")
        try:
            res = self.session.request(method, url, data=data, files=files, json=json)
        except (requests.RequestException, requests.ConnectionError) as e:
            logger.warning(f"Got an exception during {method} {url}: {e}")
            res = requests.Response()
            res.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
            return res
        if res.status_code != HTTPStatus.OK:
            msg = f"Received status_code {res.status_code} from {method} {url}"
            logger.warning(msg)
            raise ValueError(msg)
        return res

    def login(self) -> None:
        self.session = requests.Session()

        # get xsrf/csrf token (is set as cookie). Works without?
        # xsrf_page_url = "https://catcoder.codingcontest.org/"
        # self.request(method="GET", url=xsrf_page_url)
        # logger.debug(f"Received XSRF-Token {self.session.cookies['XSRF-TOKEN']}")

        # get initial SESSION cookie
        session_url = (
            f"https://catcoder.{self.contest_domain}/oauth2/authorization/"
            f"cc-registration?referer=https://catcoder.{self.contest_domain}/"
        )
        self.request(method="GET", url=session_url)
        first_session = self.session.cookies["SESSION"]
        logger.debug(f"Received first SESSION cookie {first_session}")

        # get actual SESSION cookie
        payload = {
            "username": self.ccc_username,
            "password": self.ccc_password,
        }
        login_url = f"https://register.{self.contest_domain}/auth/login"
        self.request(method="POST", url=login_url, data=payload)
        second_session = self.session.cookies["SESSION"]
        if first_session == second_session:
            logger.error(
                f"Failed login for {self.ccc_username}. Check your .env file "
                "(CCC_USERNAME + CCC_PASSWORD)"
            )
            msg = "Login Failed"
            raise ValueError(msg)
        logger.debug(f"Received second SESSION cookie {second_session}")

    def current_level_info(self) -> LevelInfo:
        res = self.request(
            method="GET",
            url=f"https://catcoder.{self.contest_domain}/api/game/input/info/{self.ccc_contest_id}",
        ).json()
        res2 = self.request(
            method="GET",
            url=f"https://catcoder.{self.contest_domain}/api/game/level/{self.ccc_contest_id}",
        ).json()
        is_input_files = res["hasInputFile"]
        assert len(res["tests"]) > 0
        if res["tests"][0]["inputsDto"][0].get("name", None) is not None:
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

    def download_level_files(self, path: Path, *, is_input_files: bool) -> Path | None:
        filetypes = ["description"]
        if is_input_files:
            filetypes.append("input")
        for filetype in filetypes:
            res = self.request(
                method="GET",
                url=f"https://catcoder.{self.contest_domain}/api/contest/{self.ccc_contest_id}/file-request/{filetype}",
            ).json()
            url = res["url"]
            res = requests.get(url, timeout=60)
            if "content-disposition" in res.headers:
                cd_header = res.headers["content-disposition"]
                filepath = path / re.findall(r'filename="(.+)"', cd_header)[0]
            else:
                filepath = path / url.split("/")[-1]
            with filepath.open("wb") as fout:
                fout.write(res.content)
        return filepath if is_input_files else None

    def upload_solution(self, path: Path, stage_name: str, *, is_output_files: bool) -> bool:
        if is_output_files:
            with path.open("rb") as fin:
                files = [("file", (path.parts[-1], fin, "text/plain"))]
                res = self.request(
                    method="POST",
                    url=f"https://catcoder.{self.contest_domain}/api/game/{self.ccc_contest_id}/upload/solution/{stage_name}",
                    files=files,  # type: ignore[arg-type]
                ).json()
        else:
            with path.open(encoding="utf-8") as fin:
                solution = next(fin).strip()  # consider only first line
                logger.debug(f"Submitting '{solution}' for stage {stage_name}")
                res = self.request(
                    method="POST",
                    url=f"https://catcoder.{self.contest_domain}/api/game/{self.ccc_contest_id}/submit",
                    json={"results": {stage_name: solution}},
                ).json()
        assert res["results"][stage_name] in {"VALID", "INVALID"}
        return res["results"][stage_name] == "VALID"  # type: ignore[no-any-return]

    def upload_source(self, path: Path) -> None:
        with path.open("rb") as fin:
            files = [("file", (path.parts[-1], fin, "text/plain"))]
            self.request(
                method="POST",
                url=f"https://catcoder.{self.contest_domain}/api/game/{self.ccc_contest_id}/1/upload",
                files=files,  # tyape: ignore
            )
