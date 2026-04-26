# Publishing

MdLens is prepared for PyPI as the distribution package `mdlens`.

The import package and command remain unchanged:

```powershell
python -m mdlens --help
mdlens --help
```

## Package Name

The PyPI name `mdlens` is already used by another project, so this project uses `mdlens` as its distribution name.

If you want a different PyPI name, change only this field before the first release:

```toml
[project]
name = "mdlens"
```

Once a version is uploaded to PyPI, the same version cannot be replaced. Bump `version` for every new release.

## Local Release Check

Run tests and build the source distribution and wheel:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run --python 3.12 --group dev pytest
uv build --no-sources
```

The build output is written to `dist/`.

## TestPyPI

Create an API token on TestPyPI, then publish to the configured `testpypi` index:

```powershell
uv publish --index testpypi --token pypi-...
```

Install from TestPyPI in a clean environment:

```powershell
uv run --with mdlens --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ --no-project -- mdlens --help
```

## PyPI

For a manual PyPI upload, create a PyPI API token and run:

```powershell
uv publish --token pypi-...
```

The repository also includes `.github/workflows/publish.yml` for Trusted Publishing. To use it:

1. Create the `mdlens` project on PyPI, or prepare a pending publisher for a new project.
2. Add a Trusted Publisher for this GitHub repository.
3. Use workflow name `.github/workflows/publish.yml`.
4. Use environment name `pypi`.
5. Create a GitHub Release. The workflow will run tests, build `dist/`, and publish to PyPI.

## Install After Release

```powershell
pipx install mdlens
mdlens C:\path\to\markdown-folder
```
