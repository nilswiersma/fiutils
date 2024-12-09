Some python code for doing FI.

# Recommended usage

1. `pip install` this package:
    ```
    cd <workdir>
    python -m venv .venv
    source .venv/bin/activate
    git clone <this>
    pip install -e <this>
    ```
2. Copy the contents of notebook to a working dir:
    ```
    cd <workdir>
    cp -rv <this>/notebooks/* ./
    ```
3. Try `python 000-simple-example.py`

# Build package

```
python -m pip install setuptools_scm build tox
python -m build
```