# OshyVPN

OshyVPN is an API service by **OshyDev**, version **0.01-BETA**. End users install `oshyVPN.exe` on Windows or `oshyvpn_0.0.1~beta_amd64.deb` on Debian/Ubuntu. Packages contain the runnable app; no language toolchains or source checkout are required.

## Install the latest Debian package

```sh
curl -fsSL https://raw.githubusercontent.com/OshyDev/oshyVPN/main/install.sh | bash
```

The installer downloads the latest release `.deb` and runs `sudo apt install` on it. To download it manually, use `curl -fL https://github.com/OshyDev/oshyVPN/releases/latest/download/oshyvpn_amd64.deb -o oshyvpn.deb && sudo apt install ./oshyvpn.deb`. To use another GitHub repository, set `OSHYVPN_REPOSITORY=owner/repo` before running `install.sh`.

## Run

Run `oshyVPN.exe` on Windows or `oshyvpn` on Debian/Ubuntu. The API listens on `127.0.0.1:8000`; open `http://127.0.0.1:8000/docs`. Use `--host` and `--port` to change the bind address. `API_KEY` enables `X-API-Key` authentication. `API_DATABASE` changes the SQLite database path.

## API

- `GET /health` and `GET /version`
- Task CRUD at `/api/tasks`
- VPN status and profile CRUD at `/api/vpn`

VPN profile routes store peer metadata only. They do not install or start a WireGuard tunnel.

## Build and release

Version and author metadata are in `oshy_service/version.py`. Push a matching tag such as `v0.01-BETA` to build the Windows executable and Debian package on their native GitHub Actions runners and attach them to a GitHub Release. Updating uses the same install command after the new release is published; the app does not self-update.

The release workflow expects the public GitHub repository `OshyDev/oshyVPN`. This workspace has no Git remote and the build dependencies (pip, FastAPI, Uvicorn, PyInstaller) are not installed, so package binaries cannot be emitted locally here. The workflow will produce `oshyVPN.exe` and `oshyvpn_0.0.1~beta_amd64.deb` once the project is pushed to that repository and the version tag is published.

For a local Linux build, install Python 3.12, the packages in `requirements.txt`, PyInstaller and `dpkg-deb`, then run:

```sh
pyinstaller --clean --onefile --collect-all uvicorn --collect-all fastapi --collect-all pydantic --name oshyVPN oshy_service/cli.py
bash packaging/build-deb.sh
```
