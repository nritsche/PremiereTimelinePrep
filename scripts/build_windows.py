"""Assemble runtime media tools and build the Windows GUI executable."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def copy_tool_folder(executable: Path, destination: Path, expected_name: str) -> None:
    if not executable.is_file():
        raise SystemExit("Missing required executable: {}".format(executable))
    destination.mkdir(parents=True, exist_ok=True)
    # Keep neighboring DLLs/data together; FFprobe builds can require side-by-side
    # DLLs and ExifTool's Windows distribution can include exiftool_files.
    for item in executable.parent.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(str(item), str(target), dirs_exist_ok=True)
        elif item.is_file():
            shutil.copy2(str(item), str(target))
    target_executable = destination / expected_name
    if executable.name.lower() != expected_name.lower():
        shutil.copy2(str(executable), str(target_executable))
    if not target_executable.exists():
        raise SystemExit("Could not stage {}".format(expected_name))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffprobe", required=True, type=Path)
    parser.add_argument("--exiftool", required=True, type=Path)
    args = parser.parse_args()
    tools_root = ROOT / "build-tools" / "tools"
    if tools_root.exists():
        shutil.rmtree(str(tools_root))
    copy_tool_folder(args.ffprobe.resolve(), tools_root / "ffprobe", "ffprobe.exe")
    copy_tool_folder(args.exiftool.resolve(), tools_root / "exiftool", "exiftool.exe")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
               "--windowed", "--name", "PremiereTimelinePrep", "--add-data",
               "{};tools".format(tools_root), str(ROOT / "app" / "main.py")]
    subprocess.run(command, cwd=str(ROOT), check=True)
    print("Windows executable: {}".format(ROOT / "dist" / "PremiereTimelinePrep.exe"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
