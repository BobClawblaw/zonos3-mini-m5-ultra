"""Settings: recipe.toml's defaults, local.toml's overrides for this Mac, then environment variables in upper case."""

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# the steering bundle: direction vectors Zyphra keeps in its code repository (MIT), not in the release
STEER_REPO = "https://github.com/Zyphra/ZONOS3-Mini"
STEER_SHA = "96d9e0ec1e39083ed336ac78f24e3dbc93721c0f"
STEER_DIR = "assets/steering"
STEER_BUNDLE = "studio_bundle_mect60k_x10.json"
# from the same repository and commit: LACI's alignment heads, and the short-text registry of its Python package
LACI_DIR = "assets/laci_heads"
SHORT_DIR = "model/src/zonos3/registries"
SHORT_FILE = "short_text.json"


@dataclass
class Settings:
    model_repo: str = ""
    model_revision: str = ""
    served_name: str = ""
    model_dir: str = ""
    tensorfold_src: str = ""
    tensorfold_sha: str = ""
    zig: str = "zig"
    zig_cpu: str = "native"
    binary: str = ""
    host: str = "127.0.0.1"
    port: int = 30117
    ui_port: int = 30118
    tf_cache: str = "~/.cache/zonos3-mini-m5"
    context: int = 4096
    parallel: int = 4
    api_key: str = ""
    steer: bool = True
    steer_bundle: str = ""
    laci: bool = True
    extra_args: str = ""

    @staticmethod
    def path(p: str) -> Path:
        return Path(os.path.expanduser(p))

    @property
    def model(self) -> Path:
        return self.path(self.model_dir)

    @property
    def cache(self) -> Path:
        return self.path(self.tf_cache)

    @property
    def worktree(self) -> Path:
        return self.cache / "engine" / self.tensorfold_sha[:12]

    @property
    def built_binary(self) -> Path:
        return self.worktree / "zig-out" / "native" / "bin" / "tensorfold-native"

    @property
    def built_textnorm(self) -> Path:
        """libzyphra_textnorm (Zyphra's text normalization), which the server loads beside its binary (../lib)."""
        return self.worktree / "zig-out" / "native" / "lib" / "libzyphra_textnorm.dylib"

    @property
    def run_binary(self) -> Path:
        return self.path(self.binary) if self.binary else self.built_binary

    @property
    def steer_src(self) -> Path:
        """Where `build` checks out the publisher's steering, LACI and short-text folders."""
        return self.cache / "steering" / STEER_SHA[:12]

    @property
    def bundle(self) -> Path | None:
        """The steering bundle the server loads: steer_bundle when set, else the one `build` fetched; None: steer is off."""
        if not self.steer:
            return None
        return self.path(self.steer_bundle) if self.steer_bundle else self.steer_src / STEER_DIR / STEER_BUNDLE

    @property
    def laci_heads(self) -> Path:
        """The folder of alignment-head files `build` fetched: what `laci` requests and short texts need."""
        return self.steer_src / LACI_DIR

    @property
    def short_text(self) -> Path:
        return self.steer_src / SHORT_DIR / SHORT_FILE

    @property
    def pid_file(self) -> Path:
        return self.cache / "server.pid"

    @property
    def log_file(self) -> Path:
        return self.cache / "server.log"

    @property
    def url(self) -> str:
        host = "127.0.0.1" if self.host in ("0.0.0.0", "") else self.host
        return f"http://{host}:{self.port}/v1"

    def serve_args(self) -> list[str]:
        a = [str(self.run_binary), "serve", "--host", self.host, "--port", str(self.port), "--name", self.served_name,
             "--context", str(self.context), "--parallel", str(self.parallel), "--no-update-check"]
        if self.api_key:
            a += ["--api-key", self.api_key]
        if self.bundle is not None:
            a += ["--steer-bundle", str(self.bundle)]
        if self.laci:
            a += ["--laci-heads", str(self.laci_heads), "--short-text", str(self.short_text)]
        a += self.extra_args.split()
        a.append(str(self.model))
        return a

    def server_env(self) -> dict[str, str]:
        return dict(os.environ)


def _coerce(kind: type, raw):
    if kind is bool:
        return raw if isinstance(raw, bool) else str(raw).lower() in ("1", "true", "yes", "on")
    return kind(raw)


def load(local_file: Path | None = None, env: dict[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    merged: dict = {}
    for f in (ROOT / "recipe.toml", local_file or ROOT / "local.toml"):
        if f.exists():
            for section in tomllib.loads(f.read_text()).values():
                merged.update(section)
    s = Settings()
    for fld in fields(Settings):
        kind = type(getattr(s, fld.name))
        if fld.name in merged:
            setattr(s, fld.name, _coerce(kind, merged[fld.name]))
        if fld.name.upper() in env:
            setattr(s, fld.name, _coerce(kind, env[fld.name.upper()]))
    return s


def validate(s: Settings) -> list[str]:
    """The settings' problems, worded for the user (empty: none)."""
    out = []
    if not s.binary and not s.tensorfold_sha:
        out.append("no engine: set tensorfold_sha (local.toml) or binary")
    if not (s.model / "lm" / "zonos3_mini" / "params.json").exists():
        out.append(f"no release at {s.model}: hf download {s.model_repo} --revision {s.model_revision} --local-dir {s.model_dir}")
    if s.context < 1025 or s.context > 32768:
        out.append("context must be 1025 to 32768")
    if not 1 <= s.parallel <= 16:
        out.append(f"parallel = {s.parallel}: the server takes 1 to 16 requests at once")
    if s.bundle is not None and not s.bundle.exists():
        out.append(f"no steering bundle at {s.bundle}: python3 -m mac build fetches it (or steer = false)")
    if s.laci and not (s.laci_heads.is_dir() and s.short_text.exists()):
        out.append(f"no LACI heads at {s.laci_heads} or no {s.short_text}: python3 -m mac build fetches them (or laci = false)")
    if not s.run_binary.exists():
        out.append(f"no engine binary at {s.run_binary}: python3 -m mac build")
    elif not s.binary and not s.built_textnorm.exists():
        out.append(f"no libzyphra_textnorm beside the engine ({s.built_textnorm}): python3 -m mac build (needs cargo)")
    return out
