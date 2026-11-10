PHASE 0 NOTES - PROJECT SKELETON
AgentBench-Lite | completed 2026-11-10 | first commit beba908
=====================================================================

These notes explain WHAT we did in Phase 0, WHY we did it, and WHAT
every term means. Use them to revise this project or to start any new
Python project on your own.


=====================================================================
PART 1 - THE BIG PICTURE
=====================================================================

Goal of Phase 0: build an empty but professional "container" for the
project BEFORE writing any real code. A good skeleton means:
  - the code can be installed like a real Python package
  - tests can be run with one command
  - secrets and junk files can never be uploaded by accident
  - the project is documented and stored safely on GitHub

What we ended with:

  AgentBench-Lite/
  |-- .gitignore            list of files Git must never track
  |-- LICENSE               legal terms (MIT)
  |-- PROJECT_STATUS.md     progress tracker
  |-- README.md             front page of the project
  |-- pyproject.toml        project configuration
  |-- docs/
  |   |-- architecture.md   planned design
  |   |-- decisions/
  |   |   `-- 0001-provider-independent-llm.md   decision record
  |   `-- learning/
  |       `-- phase-0-notes.md                   (this file)
  |-- src/
  |   `-- agentbench/
  |       `-- __init__.py   the package (only a version number for now)
  |-- tests/
  |   `-- test_smoke.py     two simple tests
  `-- .venv/                virtual environment (NOT uploaded to GitHub)


=====================================================================
PART 2 - THE STEPS WE FOLLOWED (IN ORDER)
=====================================================================

STEP 1 - Inspect before acting
  We checked the folder (dir), whether Git was already set up
  (git status), whether the GitHub repo had anything in it
  (git ls-remote <url>), the Python version, and the Git identity
  (git config --global user.name / user.email).
  WHY: never assume. If files exist you could overwrite them; if the
  GitHub repo already has a README, the first push needs extra steps.

STEP 2 - Design the structure, then create the files
  We decided the folders first (src layout, tests, docs), then created
  the configuration and documentation files.
  WHY: structure is cheap to change at the start and expensive later.
  We did NOT create empty folders for future features (llm/, tools/):
  each folder is added in the phase that needs it.

STEP 3 - Create a virtual environment
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -c "import sys; print(sys.prefix)"
    python -m pip install --upgrade pip
  WHY: a private Python for this project only (see "virtual
  environment" in Part 4).

STEP 4 - Install our package in editable mode
    python -m pip install -e ".[dev]"
  WHY: makes "import agentbench" work everywhere in the venv, and
  installs pytest.

STEP 5 - Run the tests
    pytest
  Result: 2 passed.

STEP 6 - Fix a warning, then re-verify
  setuptools warned that   license = { text = "MIT" }   is deprecated.
  We changed it to         license = "MIT"
                           license-files = ["LICENSE"]
  and required setuptools>=77. Then: reinstall -> pytest (2 passed)
  -> pip show agentbench-lite (showed "License-Expression: MIT").
  LESSON: warnings are future errors. Fix them early. And after ANY
  config change: reinstall and test again before committing.

STEP 7 - Git: initialize, connect, stage, check, commit, push
    git init -b main
    git remote add origin https://github.com/Murariji/AgentBench-Lite.git
    git remote -v
    git add .
    git status                       <- CHECK the list before committing
    git commit -m "summary" -m "body"
    git log --oneline
    git push -u origin main
    git status                       <- "up to date with 'origin/main'"


=====================================================================
PART 3 - EVERY FILE EXPLAINED
=====================================================================

--- pyproject.toml ---------------------------------------------------
The ONE configuration file for a modern Python project. Read by pip,
setuptools and pytest. Written in TOML format (sections in [brackets],
then key = value lines).

  [build-system]
    requires = ["setuptools>=77"]
    build-backend = "setuptools.build_meta"
    -> HOW to turn our source code into an installable package.
       setuptools is the tool that does it ("build backend").

  [project]
    name = "agentbench-lite"
       -> the DISTRIBUTION name: what you pip install.
    The IMPORT name is the folder: src/agentbench -> "import agentbench".
       (Same idea as: pip install scikit-learn, but import sklearn.)
    dynamic = ["version"]
       -> version is not written here; it is read from the code.
    requires-python = ">=3.11"
    license = "MIT"  + license-files = ["LICENSE"]
    dependencies = []
       -> libraries needed to RUN the project. Empty on purpose.

  [project.optional-dependencies]
    dev = ["pytest>=8"]
       -> extra libraries only developers need. Installed with ".[dev]".

  [tool.setuptools.packages.find]
    where = ["src"]
       -> "our code lives inside src/".

  [tool.setuptools.dynamic]
    version = { attr = "agentbench.__version__" }
       -> read the version from src/agentbench/__init__.py.
          ONE place to change the version = no mismatches.

  [tool.pytest.ini_options]
    testpaths = ["tests"]   -> only search tests/ for tests
    addopts = "-ra"         -> always print a summary of failures/skips

--- .gitignore -------------------------------------------------------
Patterns of files Git must NOT track. Ours ignores:
  .venv/  venv/                   virtual environment (huge, per machine)
  __pycache__/  *.py[cod]         compiled Python files (auto-generated)
  *.egg-info/  build/  dist/      build output (auto-generated)
  .pytest_cache/  .coverage ...   tool caches
  .env  .env.*                    SECRETS like API keys
  !.env.example                   "!" = exception: DO track this one
  results/  *.db  *.sqlite        data produced by running the program
  .vscode/  .idea/  Thumbs.db     editor / OS personal files
Rule of thumb: track what a HUMAN writes; ignore what a TOOL generates,
and never track secrets.

--- src/agentbench/__init__.py --------------------------------------
A folder with __init__.py is a Python "package". This file runs when
someone does "import agentbench". Ours holds only:
    __version__ = "0.1.0"
The docstring (text in triple quotes at the top) describes the package.

--- tests/test_smoke.py ---------------------------------------------
Two "smoke tests" (simplest possible "does it work at all?" checks):
  test_package_imports_and_has_version
     imports agentbench and checks __version__ is a non-empty string.
  test_package_is_installed
     importlib.metadata.version("agentbench-lite") asks pip's records
     for the installed version. It only works if the package is really
     INSTALLED, and it must equal __version__.
  pytest finds tests automatically: files named test_*.py, functions
  named test_*. "assert <condition>" fails the test if it is False.

--- README.md --------------------------------------------------------
Front page on GitHub. Says what the project is, its status, setup
commands, layout, roadmap and license. Our rule: clearly mark
"Implemented" vs "Planned" - never claim features that don't exist.

--- LICENSE ----------------------------------------------------------
Without a license, nobody may legally reuse your code. MIT = anyone may
use/modify/share it if they keep the copyright notice; no warranty.

--- PROJECT_STATUS.md ------------------------------------------------
Short progress tracker: current state, decisions, roadmap, next step.
Updated after every milestone so work can resume without re-explaining.

--- docs/architecture.md --------------------------------------------
How the parts will fit together (Runner, Tracer, Evaluator, Analyzer,
LLM layer). Labelled "planned" until built.

--- docs/decisions/0001-....md (ADR) --------------------------------
An Architecture Decision Record: a short note of ONE important decision
- Context (the problem), Decision (what we chose), Consequences (pros
and cons). Never rewritten; if a decision changes, write a new ADR.
ADR 0001: all code talks to an LLMClient interface; Gemini is the first
provider; Ollama/Groq can be added later as new modules.


=====================================================================
PART 4 - GLOSSARY (TERMS IN PLAIN LANGUAGE)
=====================================================================

PYTHON PACKAGING
  Module ............ a single .py file you can import.
  Package ........... a folder of modules with an __init__.py.
  Distribution ...... the installable bundle (name used by pip).
  Wheel (.whl) ...... the standard file format of a built package.
  Build backend ..... the tool that builds the wheel (setuptools).
  Metadata .......... info about the package (name, version, license)
                      stored when installed. "pip show" displays it.
  src layout ........ code lives in src/<package>/. Python can only
                      import it after INSTALLING, so tests check the
                      real installed package, not a file that happens
                      to be in the current folder.
  Editable install .. pip install -e . : installs a LINK to your source
                      folder instead of a copy. Edit code -> change is
                      live. Reinstall only when pyproject.toml changes.
  Extras ............ optional dependency groups, e.g. ".[dev]".
                      The "." means "the project in this folder".
  Dependency ........ a library your project needs.
  Transitive dep. ... a library needed by YOUR dependency (pytest pulled
                      in pluggy, iniconfig, colorama, packaging, pygments).
  Version specifier . ">=8" means version 8 or newer.
  SPDX .............. standard short names for licenses ("MIT").
  Deprecation ....... "this still works but will be removed later".

ENVIRONMENT
  Virtual env (venv)  a private Python + packages folder for one
                      project, so projects can't break each other.
  Activate .......... make the current terminal use the venv's python
                      and pip. Prompt shows (.venv). Per-terminal: in a
                      NEW window, activate again.
  sys.prefix ........ path of the Python currently running; proves
                      which environment is active.
  pip ............... Python's package installer. "python -m pip" =
                      the pip belonging to THIS python (safest form).
  python -m X ....... run module X with this Python.
  Execution policy .. Windows setting that may block Activate.ps1. Fix:
                      Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

TESTING
  pytest ............ the test runner. Type "pytest" to run all tests.
  Test .............. a function that checks a behaviour with assert.
  Smoke test ........ the simplest "is it alive?" test.
  "2 passed" ........ both tests ran and every assert was True.

GIT / GITHUB
  Git ............... tool that records the history of your files.
  GitHub ............ a website that hosts Git repositories online.
  Repository (repo) . a project folder tracked by Git (.git folder
                      holds the history).
  Working tree ...... your actual files on disk.
  Staging area ...... a "box" of changes chosen for the next commit
                      (git add puts things in it).
  Commit ............ a permanent snapshot + author + date + message.
  Hash .............. unique ID of a commit (ours: beba908).
  Root commit ....... the very first commit in a repo.
  Branch ............ a named line of commits. Ours: main.
  Remote / origin ... a copy of the repo elsewhere; "origin" is the
                      usual nickname for the GitHub copy.
  Push .............. upload your commits to the remote.
  Pull / fetch ...... download commits from the remote.
  Upstream (-u) ..... links local main to origin/main so plain
                      "git push"/"git pull" work afterwards.
  LF / CRLF ......... invisible line-ending characters (Linux/macOS use
                      LF, Windows CRLF). Git converts automatically; the
                      warning is harmless.
  Conventional Commits  message style "type: summary".
                      Types: feat, fix, docs, test, chore, refactor.
                      Summary in imperative mood ("add", not "added").
  ">>" in PowerShell  continuation prompt: the command isn't finished
                      (e.g. an open quote). Not an error.

PROJECT DESIGN (used from Phase 1 on)
  Agent ............. an LLM in a loop: decide -> use a tool -> look at
                      the result -> repeat -> final answer.
  Interface ......... a contract ("any LLM client must have these
                      methods"). Code depends on the contract, not on a
                      vendor, so providers are swappable.
  Provider .......... a company/tool serving an LLM (Gemini, Ollama...).
  ADR ............... Architecture Decision Record (see Part 3).


=====================================================================
PART 5 - REUSABLE CHECKLIST: START ANY NEW PYTHON PROJECT
=====================================================================

  [ ] 1. Inspect: folder contents, git status, remote repo, python
         --version, git config user.name / user.email
  [ ] 2. Create folders: src/<package>/, tests/, docs/
  [ ] 3. Write: pyproject.toml, .gitignore, README.md, LICENSE,
         src/<package>/__init__.py (with __version__),
         tests/test_smoke.py
  [ ] 4. python -m venv .venv
  [ ] 5. .\.venv\Scripts\Activate.ps1       (check prompt shows (.venv))
  [ ] 6. python -m pip install --upgrade pip
  [ ] 7. python -m pip install -e ".[dev]"  (read warnings - fix them)
  [ ] 8. pytest                             (all pass)
  [ ] 9. git init -b main
  [ ] 10. git remote add origin <repo-url>.git
  [ ] 11. git add .   then   git status     (no .venv, caches, secrets!)
  [ ] 12. git commit -m "chore: initialize project skeleton"
  [ ] 13. git push -u origin main
  [ ] 14. git status -> "up to date"; open the repo page in the browser

Everyday loop after setup:
  edit code -> pytest -> git status -> git add <files> -> git commit
  -> git push


=====================================================================
PART 6 - KEY LESSONS
=====================================================================
  1. Inspect before you change anything.
  2. Keep it minimal: add a dependency or folder only when needed.
  3. Never commit secrets; .gitignore them from day one.
  4. Warnings today are errors tomorrow - fix them early.
  5. After any config change: reinstall, re-test, THEN commit.
  6. Always read "git status" before "git commit".
  7. Only record verified facts in status files and READMEs.
