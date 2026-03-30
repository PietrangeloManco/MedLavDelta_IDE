# medicina_lavoro

## Setup notes

This project installs Python dependencies from `requirements.txt`.

Some packages used by `svglib` require Cairo system libraries to be present before
`pip install -r requirements.txt` will succeed on Ubuntu/Debian systems.

Install them with:

```bash
apt-get update
apt-get install -y pkg-config libcairo2-dev python3-dev build-essential
```

Then install the Python dependencies:

```bash
pip install -r requirements.txt
```
