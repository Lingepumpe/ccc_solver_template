# Template for Coding Contests

Optimized for https://catcoder.codingcontest.org

Template for fast solving of catcoder codingcontests, with two command line
utilities:

## next-level command

- Logs into catcoder for you, checks your current level
- Creates folder for current level, code copied from previous level or template
  Folder created: codingcontest/level${LVL_NUMBER}
- Fetches pdf+zip of current level from catcoder
- Extracts zip, input files to in/, out/ subfolders
- Creates git commit at level start, and pushes

## submit-solutions command

- Checks outputfiles from out/ subfolder of current level, checks files with cat-coder
- Aborts on first unsuccessful file
- If all successful: Creates git commit for level end, and pushes. Runs `next-level`
  for you if there are more levels.
- If some successful, but not all: Creates git commit for level progress, and pushes

## Installation

To install:

- Pre0) Install/Activate python 3.10.x or 3.11.x (e.g. with pyenv on linux)
- Pre1) Install poetry (recommended way: via pipx):
  ```shell
    pip install --upgrade pip
    pip install --user pipx
    python -m pipx ensurepath
    # Maybe restart shell if pipx command cannot be found
    pipx install poetry
  ```

1. From the project root:
   `poetry install`

2. Activate environment via
   `poetry shell`

=> You now have access to the command line command `next-level` and
`submit-sollution`.

If you want additional libraries/packages, install them via:
`poetry add dependency`

## Setting up

### Create .env file

In the repository root, create a file called `.env`. Example:

```
CCC_USERNAME=catcoder_username_or_email
CCC_PASSWORD=catcoder_password
CCC_CONTEST_ID=<from URL of contest, e.g. 4344>
CCC_GIT_MODE=<none|local|remote>
CCC_SOLUTION_SUBMIT_FILE=solution.py
```

- Username (can be an email) + Password of the catcoder login.
- Contest ID can be found in the contest URL, e.g.
  `https://catcoder.codingcontest.org/training/140/play` is `140`.
- GIT_MODE:
  - none disables any git actions
  - local enables only local actions (creating commits for new
    level + successful submissions)
  - remote is like local, but also runs git pull + git push for you
- CCC_SOLUTION_SUBMIT_FILE:
  If set to a valid file within your template/level structure, it will
  submit this file as "your solution" after completing each level, to
  give you some bonus minutes. If not set to a valid file, you will not
  recieve bonus minutes for handing in your solution code.

### Git setup (optional)

Copy this code to your own git repo (or change the remotes). If you
want remote git support, make sure you can pull and push. For local
git support, make sure you can commit.

### Competing

- Edit codingcontest/template to your liking, it is your starting point
  for level1.
- Run `next-level`, this should create codingcontest/level1/
- while not done:
  - Edit solver code (solver.py if you are using the python template)
  - Python solver.py will submit and call next level once the level is done.
  - Otherwise, you can run `submit-solutions` manually to validate your .out files.
  - If a level is complete, `submit-solutions` will automatically run `next-level`
