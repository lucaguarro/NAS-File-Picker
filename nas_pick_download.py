#!/usr/bin/env python3
import os
import shlex
import subprocess
from pathlib import Path

NAS_HOST = "indonas_lan"          # ssh config host or user@host
REMOTE_ROOT = "/mnt/media1/Games"
LOCAL_DEST = str(Path.home() / "Downloads")
USE_RSYNC = True                  # set False to use scp

def run(cmd: str) -> str:
    p = subprocess.run(cmd, shell=True, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed:\n{cmd}\n\nstderr:\n{p.stderr}")
    return p.stdout

def list_remote(remote_dir: str) -> list[str]:
    # -p appends / to directories
    cmd = f"ssh {shlex.quote(NAS_HOST)} {shlex.quote(f'cd {remote_dir} && ls -1p')}"
    out = run(cmd)
    items = [x for x in out.splitlines() if x.strip()]
    return items

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
        # either user hit Esc (empty) or picked something but fzf gave single line
        return ("", out[0].strip())
    key = out[0].strip()          # "" or "ctrl-d"
    sel = out[1].strip()
    return (key, sel)

def download_rsync(remote_path: str, local_dest: str):
    os.makedirs(local_dest, exist_ok=True)
    cmd = ["rsync", "-avP", "--protect-args", f"{NAS_HOST}:{remote_path}", local_dest + "/"]
    subprocess.check_call(cmd)

def download_scp(remote_path: str, local_dest: str, is_dir: bool):
    os.makedirs(local_dest, exist_ok=True)
    cmd = ["scp"]
    if is_dir:
        cmd += ["-r"]
    cmd += ["-p", f"{NAS_HOST}:{remote_path}", local_dest + "/"]
    subprocess.check_call(cmd)

def download(remote_path: str, local_dest: str, is_dir: bool):
    if USE_RSYNC:
        # rsync handles files and dirs with same syntax (dirs copy recursively by default)
        download_rsync(remote_path, local_dest)
    else:
        download_scp(remote_path, local_dest, is_dir=is_dir)

def main():
    remote_dir = REMOTE_ROOT

    while True:
        items = list_remote(remote_dir)

        # Only real selectable entries. Add ../ ourselves.
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
                download(dir_path, LOCAL_DEST, is_dir=True)
                print("✅ Done.")
                return 0
            else:
                # Enter directory
                remote_dir = dir_path
                continue

        # file selected (Enter)
        file_path = str(Path(remote_dir) / choice)
        print(f"⬇ Downloading file: {file_path}")
        download(file_path, LOCAL_DEST, is_dir=False)
        print("✅ Done.")
        return 0

if __name__ == "__main__":
    main()
