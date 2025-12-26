#!/usr/bin/env python3
import os
import shlex
import subprocess
from pathlib import Path

# --- Config loading (TOML) ---
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # Python 3.10 and older
    import tomli as tomllib  # pip install tomli


DEFAULTS = {
    "nas_host": "indonas_lan",          # ssh config host or user@host
    "remote_root": "/mnt/media1/Games",
    "local_dest": str(Path.home() / "Downloads"),
    "use_rsync": True,
}

CONFIG_PATH = Path(os.environ.get("NAS_FETCH_CONFIG", "~/.config/nas_fetch/config.toml")).expanduser()


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("rb") as f:
            data = tomllib.load(f)
        if not isinstance(data, dict):
            raise RuntimeError(f"Config must be a TOML table at top-level: {CONFIG_PATH}")
        cfg.update({k: v for k, v in data.items() if v is not None})

    # Normalize / validate
    cfg["local_dest"] = str(Path(str(cfg["local_dest"])).expanduser())
    cfg["remote_root"] = str(cfg["remote_root"])
    cfg["nas_host"] = str(cfg["nas_host"])
    cfg["use_rsync"] = bool(cfg["use_rsync"])
    return cfg


def run(cmd: str) -> str:
    p = subprocess.run(cmd, shell=True, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed:\n{cmd}\n\nstderr:\n{p.stderr}")
    return p.stdout


def list_remote(nas_host: str, remote_dir: str) -> list[str]:
    cmd = f"ssh {shlex.quote(nas_host)} {shlex.quote(f'cd {remote_dir} && ls -1p')}"
    out = run(cmd)
    return [x for x in out.splitlines() if x.strip()]


def pick_with_fzf(lines: list[str]) -> tuple[str, str]:
    """
    Returns (key, selection). key is "" for Enter, or "ctrl-d" for Ctrl-D.
    """
    p = subprocess.run(
        ["fzf", "--height=90%", "--reverse",
         "--prompt=NAS> ",
         "--header=Enter: open dir / download file | Ctrl-D: download dir | Esc: quit",
         "--expect=ctrl-d"],
        input="".join(lines),
        text=True,
        stdout=subprocess.PIPE
    )
    out = p.stdout.splitlines()
    if not out:
        return ("", "")
    if len(out) == 1:
        return ("", out[0].strip())
    key = out[0].strip()
    sel = out[1].strip()
    return (key, sel)


def download_rsync(nas_host: str, remote_path: str, local_dest: str):
    os.makedirs(local_dest, exist_ok=True)
    cmd = ["rsync", "-avP", "--protect-args", f"{nas_host}:{remote_path}", local_dest + "/"]
    subprocess.check_call(cmd)


def download_scp(nas_host: str, remote_path: str, local_dest: str, is_dir: bool):
    os.makedirs(local_dest, exist_ok=True)
    cmd = ["scp"]
    if is_dir:
        cmd += ["-r"]
    cmd += ["-p", f"{nas_host}:{remote_path}", local_dest + "/"]
    subprocess.check_call(cmd)


def download(nas_host: str, use_rsync: bool, remote_path: str, local_dest: str, is_dir: bool):
    if use_rsync:
        download_rsync(nas_host, remote_path, local_dest)
    else:
        download_scp(nas_host, remote_path, local_dest, is_dir=is_dir)


def main():
    cfg = load_config()

    NAS_HOST = cfg["nas_host"]
    REMOTE_ROOT = cfg["remote_root"]
    LOCAL_DEST = cfg["local_dest"]
    USE_RSYNC = cfg["use_rsync"]

    remote_dir = REMOTE_ROOT

    while True:
        items = list_remote(NAS_HOST, remote_dir)
        lines = ["../\n"] + [x + "\n" for x in items]
        key, choice = pick_with_fzf(lines)

        if not choice:
            print("No selection, exiting.")
            return 0

        if choice == "../":
            if remote_dir != "/":
                remote_dir = str(Path(remote_dir).parent)
            continue

        is_dir = choice.endswith("/")

        if is_dir:
            dir_path = str(Path(remote_dir) / choice[:-1])

            if key == "ctrl-d":
                print(f"⬇ Downloading directory: {dir_path}")
                download(NAS_HOST, USE_RSYNC, dir_path, LOCAL_DEST, is_dir=True)
                print("✅ Done.")
                return 0
            else:
                remote_dir = dir_path
                continue

        file_path = str(Path(remote_dir) / choice)
        print(f"⬇ Downloading file: {file_path}")
        download(NAS_HOST, USE_RSYNC, file_path, LOCAL_DEST, is_dir=False)
        print("✅ Done.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
