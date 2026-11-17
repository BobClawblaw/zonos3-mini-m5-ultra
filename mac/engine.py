"""The engine: a worktree of the TensorFold checkout at the pinned commit, built under tf_cache (never in the
checkout), and libzyphra_textnorm (text normalization) from Zyphra's zyphra-textnorm at the release the engine names,
built with cargo into the lib folder the server loads from. The zonos3 Metal port is not on ashhart/TensorFold's main
yet, so a clone without the pin fetches it from the fork's branch."""

import shutil
import subprocess
from pathlib import Path

from .config import Settings

# zyphra-textnorm's release the engine's text normalization loads (docs/recipes/zonos3-mini.md), and its commit
TEXTNORM_TAG = "0.2.0"
TEXTNORM_COMMIT = "170c571e75034c9a9f3bece9885c36d8dae77df2"
TEXTNORM_REPO = "https://github.com/Zyphra/zyphra-textnorm"

# where tensorfold_sha lives until ashhart/TensorFold#3732 lands
TENSORFOLD_REPO = "https://github.com/BobClawblaw/TensorFold"
TENSORFOLD_BRANCH = "zonos3-metal"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def build_engine(s: Settings, rebuild: bool = False) -> Path:
    if s.binary:
        return s.run_binary
    if not s.tensorfold_sha:
        raise SystemExit("no tensorfold_sha pinned (local.toml)")
    src = s.path(s.tensorfold_src)
    have = subprocess.run(["git", "-C", str(src), "cat-file", "-e", f"{s.tensorfold_sha}^{{commit}}"], capture_output=True)
    if have.returncode != 0:  # a clone without the pin
        _run(["git", "-C", str(src), "fetch", TENSORFOLD_REPO, TENSORFOLD_BRANCH])
    if not s.worktree.exists():
        s.worktree.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "-C", str(src), "worktree", "add", "--detach", str(s.worktree), s.tensorfold_sha])
    if rebuild or not s.built_binary.exists():
        _run([s.path(s.zig).as_posix(), "build", "native", "-Doptimize=ReleaseFast", f"-Dcpu={s.zig_cpu}"], cwd=s.worktree)
    return s.built_binary


def build_textnorm(s: Settings, rebuild: bool = False) -> Path:
    """libzyphra_textnorm beside the binary (../lib), which the server loads at the first request that normalizes:
    zyphra-textnorm cloned once into tf_cache at the pinned commit, built with its C interface as a cdylib."""
    if s.binary or (s.built_textnorm.exists() and not rebuild):
        return s.built_textnorm
    root = s.cache / "zyphra-textnorm"
    if not (root / ".git").exists():
        _run(["git", "clone", TEXTNORM_REPO, str(root)])
    _run(["git", "-C", str(root), "checkout", "--detach", TEXTNORM_COMMIT])
    _run(["cargo", "rustc", "--release", "--locked", "--lib", "-p", "zyphra-textnorm", "--features", "capi",
          "--crate-type", "cdylib"], cwd=root)
    built = root / "target" / "release" / "libzyphra_textnorm.dylib"
    if not built.exists():
        raise SystemExit(f"the build left no {built}")
    s.built_textnorm.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, s.built_textnorm)
    return s.built_textnorm


def build(s: Settings, rebuild: bool = False) -> Path:
    binary = build_engine(s, rebuild)
    build_textnorm(s, rebuild)
    return binary
