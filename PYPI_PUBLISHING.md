# Publishing CAT to PyPI

CAT branding: the project is **CAT** (Coding Agent Terminal).
The PyPI distribution name is **`cct-cli`** and the terminal command is **`cat`**
(plus aliases `catx` and `cct`).

```text
PyPI package: cct-cli   (no exact PyPI match — verified 2026-09-21, JSON 404.
NOTE: `cat-cli` also returned 404 but was rejected at upload by PyPI's
similarity check vs the existing `catcli` project — a 404 does NOT prove
upload acceptance, only a successful upload does.)
CLI command:  cat
```

Do **NOT** publish under `cot-ai-ide` (typo) or assume bare `cat` is free —
bare `cat` on PyPI is TAKEN (0.0.1, unrelated project). Re-check availability
immediately before the first upload:

```powershell
# Browser check (most reliable):
#   https://pypi.org/project/cct-cli/  → 404 = available
python -m pip index versions cct-cli
```

## Prerequisites

- Python 3.10+ (builds tested on 3.12; 3.10–3.13 supported per
  `pyproject.toml`). Python 3.14 is NOT claimed — see compatibility notes below.
- A PyPI account with 2FA, and a TestPyPI account for the dry run.
- Maintainer: Kazi Zillani. Repository: <https://github.com/kazizillani-oss/CAT_v0.7.9>

## 1. Build

From the repository root (`CAT_v0.7.9/`, where the canonical `pyproject.toml`
lives — it points at the real sources under `CAT_v0.7.4/` via
`package-dir = {"" = "CAT_v0.7.4"}`):

```powershell
python -m pip install --upgrade build twine
python -m build
```

Expected output:

```text
dist/
    cct_cli-0.7.9.0-py3-none-any.whl
    cct_cli-0.7.9.0.tar.gz
```

Validate before uploading:

```powershell
python -m twine check dist/*
# Expected: "Checking dist/...: PASSED"
```

Spot-check the wheel contains code + assets + entry points:

```powershell
python -c "import zipfile, pathlib; z = zipfile.ZipFile(sorted(pathlib.Path('dist').glob('*.whl'))[0]); names = z.namelist(); print('cat.ico:', any('cat.ico' in n for n in names)); print('models json:', any('model_metadata.json' in n for n in names)); print('providers json:', any('providers/providers.json' in n for n in names)); print('static:', any('web/static' in n for n in names)); print([n for n in names if 'entry_points' in n])"
```

Entry points must be:

```ini
[console_scripts]
cat = calc_terminal.cli:main
catx = calc_terminal.cli:main
cct = calc_terminal.cli:main
```

## 2. Test locally (clean virtual environment)

Never publish without installing the built wheel in a fresh venv first:

```powershell
python -m venv .venv-pypitest
.venv-pypitest\Scripts\activate
python -m pip install --upgrade pip
python -m pip install dist\cct_cli-0.7.9.0-py3-none-any.whl
cat.exe --version     # NOTE: bare `cat` is a PowerShell alias for Get-Content; use cat.exe/catx
catx --version
python -c "import calc_terminal, calc_terminal.cli, calc_terminal.app; print('imports OK', calc_terminal.__version__)"
python -c "from calc_terminal.first_run import data_dir; from calc_terminal.terminal_identity import get_icon_path; import pathlib, calc_terminal; p = pathlib.Path(calc_terminal.__file__).parent; print('pkg:', p); print('cat.ico:', (p / 'cat.ico').exists()); print('models:', (p / 'models' / 'model_metadata.json').exists()); print('providers:', (p / 'providers' / 'providers.json').exists()); print('static:', (p / 'web' / 'static' / 'index.html').exists())"
cat.exe --help
cat.exe --doctor
deactivate
```

What to verify:

- `cat.exe --version` prints `CAT v0.7.9.0`, `--help` shows usage.
- Imports work with no source-repository path on `sys.path`.
- `cat.ico`, `models/model_metadata.json`, `providers/providers.json`,
  `web/static/*` exist inside `site-packages/calc_terminal/`.
- First run seeds `%LOCALAPPDATA%\CCT` (Windows) without touching the repo.
- Themes/UI load (Textual + Rich); provider/model commands degrade gracefully
  without API keys.

## 3. Upload to TestPyPI first

Create a TestPyPI account at <https://test.pypi.org/account/register/>, then
create an API token at <https://test.pypi.org/manage/account/token/> with scope
limited to the `cct-cli` project (or "entire account" for the very first upload).

Configure the token securely — **never commit it to the repository**.
Use one of:

```powershell
# Option A: keyring-backed (recommended, nothing on disk)
python -m pip install keyring
python -m twine upload --repository testpypi dist/*   # username: __token__, password: pypi-... (paste token)
```

```powershell
# Option B: %USERPROFILE%\.pypirc (chmod-protected, never commit)
# [testpypi]
# username = __token__
# password = pypi-TEST-TOKEN-HERE
python -m twine upload --repository testpypi dist/*
```

Test-install from TestPyPI in a fresh venv:

```powershell
python -m venv .venv-testpypi
.venv-testpypi\Scripts\activate
python -m pip install --upgrade pip
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ cct-cli
cat.exe --version
```

## 4. Production PyPI publish

1. Re-check `https://pypi.org/project/cct-cli/` is still free.
2. Bump `version` in **both** `pyproject.toml` (root) and
   `CAT_v0.7.4/pyproject.toml` (mirror) if this is a new release, and bump
   `calc_terminal/__init__.py` + `calc_terminal/app.py::VERSION` to match.
3. Rebuild + re-validate: `python -m build; python -m twine check dist/*`.
4. Create a scoped production token at <https://pypi.org/manage/account/token/>
   (scope: project `cct-cli`), then:

```powershell
python -m twine upload dist/*
# username: __token__
# password: pypi-PRODUCTION-TOKEN-HERE  (paste, never store in git)
```

5. Verify in a clean machine/venv:

```powershell
python -m pip install cct-cli
cat.exe --version
cat
```

## 5. GitHub Actions (trusted publishing, no stored tokens)

`.github/workflows/python-publish.yml` publishes on GitHub Release (`published`
event) via PyPI **trusted publishing** (OIDC `id-token: write`), so no API
token is stored in secrets. One-time setup on PyPI:

1. PyPI → `cct-cli` → Settings → Publishing → Add a new pending publisher:
   owner `kazizillani-oss`, repository `CAT_v0.7.9`, workflow
   `python-publish.yml`, environment `pypi`.
2. Create a GitHub Release → the workflow builds (`python -m build`),
   uploads the artifact, and publishes with
   `pypa/gh-action-pypi-publish@release/v1`.
3. `.github/workflows/cat-package.yml` (packaging validation) runs on every
   push/PR across Python 3.10–3.13: build, `twine check`, wheel install,
   `cat --version` / `--help` smoke test. It never publishes.

## 6. Python compatibility notes

- Supported: 3.10, 3.11, 3.12, 3.13 (`requires-python = ">=3.10"`).
- 3.12 verified locally (primary build/test interpreter).
- 3.13 supported via classifiers; CI covers it. Re-run the clean-venv test
  on 3.13 before claiming it in release notes if your local machine only has
  3.12.
- 3.14 NOT claimed: `textual`, `rich`, `watchdog`, and CAT's own UI code have
  no verified 3.14 support matrix yet. The package installs on 3.14 in testing
  but 3.14 must not be added to classifiers until `cat --version`, `--help`,
  theme/UI smoke tests, and the full test-suite pass there. See `pyproject.toml`.

## 7. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `cat --version` prints a file (`Get-Content`) | PowerShell `cat` alias shadowed the CLI. Use `cat.exe --version` or `catx --version`. |
| `Missing static/index.html` | Wheel built without package-data. Rebuild from repo root; check `[tool.setuptools.package-data]` for `calc_terminal.web`. |
| `models.json/providers.json not seeded` | Same as above for `calc_terminal.models` / `calc_terminal.providers` JSON. |
| `ImportError: calc_terminal` after install | Installed from wrong directory or stale `package-dir`. Always build from repo root. |
| `twine check` FAILED (README) | `readme = "README.md"` must be repo-root README; long description must render as Markdown. |
| Version mismatch (`cat --version` ≠ PyPI) | Keep root `pyproject.toml`, `CAT_v0.7.4/pyproject.toml`, `calc_terminal/__init__.py`, `app.VERSION` in sync. |
