"""Build and smoke-test the Windows .exe and Linux .deb installers from a qualified release (v6.6.2).

Installers are always built from the exact source/web archives that scripts/package_release.py produced for the
qualified commit, so every main release ships installers of its latest code. Research data never lives inside the
installation: an installed copy carries backend.core.config.INSTALL_MARKER and stores data per user.

    python scripts/build_installers.py windows --assets output/release/assets --out output/release/windows
    python scripts/build_installers.py deb     --assets output/release/assets --out output/release/linux
    python scripts/build_installers.py smoke-windows --installer <setup.exe>
    python scripts/build_installers.py smoke-deb --deb <file.deb>
    python scripts/build_installers.py merge --assets output/release/assets --add <dir> [<dir> ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON_EMBED = {  # python.org 3.12.10 embeddable (MD5 fe8ef205f2e9c3ba44d0cf9954e1abd3 published by python.org)
    "url": "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip",
    "sha256": "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3",
    "pth": "python312._pth",
}
DEB_PYTHONS = ("3.11", "3.12", "3.13")  # wheels bundled for every supported system python3
LOCK = "requirements-runtime.lock"
INSTALL_MARKER = "phdlab-installed.json"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def asset_record(path: Path) -> dict:
    return {"name": path.name, "size": path.stat().st_size, "sha256": sha256(path)}


def release_inputs(assets: Path) -> tuple[dict, Path, Path]:
    """The qualified manifest and its verified source/web archives."""
    manifest = json.loads((assets / "manifest.json").read_text("utf-8"))
    version = manifest["version"]
    files = {}
    for kind in ("source", "web"):
        name = f"phdlab-{version}-{kind}.zip"
        record = next(a for a in manifest["assets"] if a["name"] == name)
        path = assets / name
        if sha256(path) != record["sha256"]:
            raise ValueError("Release archive does not match its manifest: " + name)
        files[kind] = path
    return manifest, files["source"], files["web"]


def _extract(archive: Path, dest: Path) -> None:
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            target = (dest / info.filename).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise ValueError("Unsafe archive entry: " + info.filename)
        z.extractall(dest)


def stage_app(assets: Path, app: Path) -> dict:
    """Unpack the qualified source and web build into app/ and mark it as an installed copy."""
    manifest, source, web = release_inputs(assets)
    app.mkdir(parents=True)
    _extract(source, app)
    dist = app / "frontend" / "dist"
    shutil.rmtree(dist, ignore_errors=True)
    dist.mkdir(parents=True)
    _extract(web, dist)
    marker = {"version": manifest["version"], "source_sha": manifest["source_sha"],
              "data": "per-user folder; see backend.core.config.user_data_dir"}
    (app / INSTALL_MARKER).write_text(json.dumps(marker, indent=2) + "\n", "utf-8")
    return manifest


def fetch_embed(cache: Path) -> Path:
    target = cache / Path(PYTHON_EMBED["url"]).name
    if not target.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(PYTHON_EMBED["url"], timeout=120) as response, target.open("wb") as out:
            shutil.copyfileobj(response, out)
    if sha256(target) != PYTHON_EMBED["sha256"]:
        target.unlink()
        raise ValueError("Embedded Python download does not match the pinned SHA-256")
    return target


def iscc() -> str:
    found = shutil.which("ISCC") or shutil.which("iscc")
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        for candidate in (Path(base) / "Programs" / "Inno Setup 6" / "ISCC.exe", Path(base) / "Inno Setup 6" / "ISCC.exe"):
            if not found and base and candidate.is_file():
                found = str(candidate)
    if not found:
        raise FileNotFoundError("Inno Setup 6 (ISCC.exe) is required to build the Windows installer")
    return found


def build_windows(assets: Path, out: Path, cache: Path) -> Path:
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Build the Windows installer with Python 3.12 (wheels must match the embedded 3.12)")
    work = Path(tempfile.mkdtemp(prefix="phdlab-win-"))
    try:
        stage = work / "stage"
        manifest = stage_app(assets, stage / "app")
        python = stage / "python"
        _extract(fetch_embed(cache), python)
        site = python / "Lib" / "site-packages"
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-deps",
                        "--require-hashes", "--only-binary=:all:", "--target", str(site), "-r", str(ROOT / LOCK)], check=True)
        # The embedded interpreter ignores PYTHONPATH; its ._pth file is the import path (site enables .pth files).
        (python / PYTHON_EMBED["pth"]).write_text("python312.zip\n.\nLib\\site-packages\n..\\app\nimport site\n", "utf-8")
        shutil.copy2(ROOT / "packaging" / "icons" / "phdlab.ico", stage / "phdlab.ico")
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run([iscc(), "/Q", f"/DAppVersion={manifest['version']}", f"/DStageDir={stage}", f"/DOutputDir={out.resolve()}",
                        str(ROOT / "packaging" / "windows" / "phdlab.iss")], check=True)
        setup = out / f"phdlab-{manifest['version']}-windows-x64-setup.exe"
        (out / (setup.name + ".json")).write_text(json.dumps(asset_record(setup)), "utf-8")
        return setup
    finally:
        shutil.rmtree(work, ignore_errors=True)


def lf_copy(source: Path, target: Path, replace: dict | None = None) -> None:
    """Package scripts and metadata always get LF endings (a CRLF postinst or control file breaks dpkg)."""
    text = source.read_bytes().decode("utf-8").replace("\r\n", "\n")
    for key, value in (replace or {}).items():
        text = text.replace(key, value)
    target.write_bytes(text.encode("utf-8"))


def build_deb(assets: Path, out: Path) -> Path:
    work = Path(tempfile.mkdtemp(prefix="phdlab-deb-"))
    try:
        tree = work / "tree"
        manifest = stage_app(assets, tree / "opt" / "phdlab" / "app")
        version = manifest["version"]
        opt = tree / "opt" / "phdlab"
        shutil.copy2(ROOT / LOCK, opt / LOCK)
        wheels = opt / "wheels"
        for py in DEB_PYTHONS:
            subprocess.run([sys.executable, "-m", "pip", "download", "--quiet", "--disable-pip-version-check", "--no-deps",
                            "--require-hashes", "--only-binary=:all:", "--python-version", py, "--implementation", "cp",
                            "--platform", "manylinux_2_28_x86_64", "--platform", "manylinux_2_17_x86_64",
                            "--platform", "manylinux2014_x86_64", "--platform", "any",
                            "--dest", str(wheels), "-r", str(ROOT / LOCK)], check=True)
        linux = ROOT / "packaging" / "linux"
        (tree / "usr" / "bin").mkdir(parents=True)
        lf_copy(linux / "phdlab", tree / "usr" / "bin" / "phdlab")
        (tree / "usr" / "share" / "applications").mkdir(parents=True)
        lf_copy(linux / "phdlab.desktop", tree / "usr" / "share" / "applications" / "phdlab.desktop")
        for size in ICON_SIZES:
            icon_dir = tree / "usr" / "share" / "icons" / "hicolor" / f"{size}x{size}" / "apps"
            icon_dir.mkdir(parents=True)
            shutil.copy2(ROOT / "packaging" / "icons" / f"phdlab-{size}.png", icon_dir / "phdlab.png")
        debian = tree / "DEBIAN"
        debian.mkdir()
        lf_copy(linux / "control.in", debian / "control", {"@VERSION@": version})
        for script in ("postinst", "prerm"):
            lf_copy(linux / script, debian / script)
        for path in (debian / "postinst", debian / "prerm", tree / "usr" / "bin" / "phdlab"):
            path.chmod(0o755)
        out.mkdir(parents=True, exist_ok=True)
        deb = out / f"phdlab_{version}_amd64.deb"
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(tree), str(deb)], check=True)
        (out / (deb.name + ".json")).write_text(json.dumps(asset_record(deb)), "utf-8")
        return deb
    finally:
        shutil.rmtree(work, ignore_errors=True)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_health(port: int, proc: subprocess.Popen, timeout: float = 180) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Installed application exited with code {proc.returncode}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=3) as response:
                return json.loads(response.read())
        except OSError:
            time.sleep(1)
    raise TimeoutError("Installed application did not answer /api/version")


def run_installed(command: list[str], env: dict, expect_version: str, data_dir: Path, install_dir: Path) -> dict:
    """Start the installed copy, check health and where it keeps data, then stop it."""
    port = free_port()
    log = Path(tempfile.mkdtemp(prefix="phdlab-smoke-")) / "server.log"
    with log.open("wb") as stream:
        proc = subprocess.Popen(command + ["--no-browser", "--port", str(port)], env=env, stdout=stream, stderr=subprocess.STDOUT)
        try:
            info = wait_health(port, proc)
        except Exception:
            proc.kill()
            print(log.read_text("utf-8", "replace")[-4000:])
            raise
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
    if info.get("version") != expect_version:
        raise RuntimeError(f"Installed version {info.get('version')} != {expect_version}")
    if not (data_dir / "config.json").is_file():
        raise RuntimeError(f"Data was not created in the per-user folder {data_dir}")
    if any(install_dir.rglob("config.json")) and any(p.parent.name == "data" for p in install_dir.rglob("config.json")):
        raise RuntimeError("Data was written inside the installation folder")
    return info


def smoke_windows(installer: Path, version: str) -> dict:
    work = Path(tempfile.mkdtemp(prefix="phdlab-winsmoke-"))
    install_dir, local = work / "install", work / "localappdata"
    local.mkdir()
    subprocess.run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/NOICONS",
                    f"/DIR={install_dir}"], check=True, timeout=600)
    env = {**os.environ, "LOCALAPPDATA": str(local)}
    env.pop("PHDLAB_DATA_DIR", None)
    info = run_installed([str(install_dir / "python" / "python.exe"), str(install_dir / "app" / "start.py")], env, version,
                         local / "PhDLab", install_dir)
    uninstaller = next(install_dir.glob("unins*.exe"))
    subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], check=True, timeout=600)
    for _ in range(60):  # the uninstaller finishes in a detached copy of itself
        if not (install_dir / "app").exists():
            break
        time.sleep(1)
    if (install_dir / "app").exists() or (install_dir / "python").exists():
        raise RuntimeError("Uninstall left the application behind")
    if not (local / "PhDLab" / "config.json").is_file():
        raise RuntimeError("Uninstall removed research data")
    return {"installed": True, "health": info, "uninstalled": True, "data_kept": True}


def smoke_deb(deb: Path, version: str) -> dict:
    sudo = [] if os.geteuid() == 0 else ["sudo"]
    subprocess.run(sudo + ["apt-get", "install", "-y", "-qq", str(deb.resolve())], check=True, timeout=900)
    home = Path(tempfile.mkdtemp(prefix="phdlab-debsmoke-"))
    env = {**os.environ, "XDG_DATA_HOME": str(home)}
    env.pop("PHDLAB_DATA_DIR", None)
    info = run_installed(["/usr/bin/phdlab"], env, version, home / "phdlab", Path("/opt/phdlab"))
    for size in ICON_SIZES:
        if not Path(f"/usr/share/icons/hicolor/{size}x{size}/apps/phdlab.png").is_file():
            raise RuntimeError("Missing PhD Lab icon " + str(size))
    subprocess.run(sudo + ["apt-get", "remove", "-y", "-qq", "phdlab"], check=True, timeout=600)
    if Path("/opt/phdlab/app").exists() or Path("/usr/bin/phdlab").exists():
        raise RuntimeError("Package removal left the application behind")
    if not (home / "phdlab" / "config.json").is_file():
        raise RuntimeError("Package removal removed research data")
    return {"installed": True, "health": info, "uninstalled": True, "data_kept": True}


def merge(assets: Path, extra_dirs: list[Path]) -> dict:
    """Add verified installer records to the qualified release manifest (source and web stay first)."""
    manifest_path = assets / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    names = {a["name"] for a in manifest["assets"]}
    for folder in extra_dirs:
        for record_path in sorted(folder.glob("*.json")):
            record = json.loads(record_path.read_text("utf-8"))
            path = folder / record["name"]
            if asset_record(path) != record:
                raise ValueError("Installer does not match its build record: " + record["name"])
            if record["name"] in names:
                raise ValueError("Duplicate release asset: " + record["name"])
            shutil.copy2(path, assets / record["name"])
            manifest["assets"].append(record)
            names.add(record["name"])
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", "utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("windows", "deb"):
        p = sub.add_parser(name)
        p.add_argument("--assets", type=Path, required=True)
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--cache", type=Path, default=ROOT / "output" / "release" / "cache")
    p = sub.add_parser("smoke-windows"); p.add_argument("--installer", type=Path, required=True); p.add_argument("--version", required=True)
    p = sub.add_parser("smoke-deb"); p.add_argument("--deb", type=Path, required=True); p.add_argument("--version", required=True)
    p = sub.add_parser("merge"); p.add_argument("--assets", type=Path, required=True); p.add_argument("--add", type=Path, nargs="+", required=True)
    args = parser.parse_args(argv)
    if args.command == "windows":
        print(build_windows(args.assets, args.out, args.cache))
    elif args.command == "deb":
        print(build_deb(args.assets, args.out))
    elif args.command == "smoke-windows":
        print(json.dumps(smoke_windows(args.installer, args.version)))
    elif args.command == "smoke-deb":
        print(json.dumps(smoke_deb(args.deb, args.version)))
    else:
        print(json.dumps(merge(args.assets, args.add)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
