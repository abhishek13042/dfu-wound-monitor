"""Shared fixtures: a tiny, randomly initialised segmentation artifact.

The real SPEC-02-03 checkpoint (293 MB, gitignored) is never needed by the
test suite.  The fixture writes a ResNet18 U-Net (``pretrained=False``) with a
64x64 input, plus matching training and inference configs, once per session.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from src.segmentation.resnet_unet import ResNetUNet

DECODER = [32, 16, 16, 8, 8]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_artifact(root: Path, *, seed: int = 0, threshold: float = 0.4, min_area: int = 4) -> Path:
    """Write checkpoint + configs under ``root``; return the inference config path."""

    root.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(seed)
    model = ResNetUNet("resnet18", pretrained=False, decoder_channels=DECODER)
    checkpoint = root / "tiny.pth"
    torch.save({"model_state_dict": model.state_dict(), "epoch": 1, "best_metric_value": 0.5}, checkpoint)
    training = {
        "preprocessing": {"input_height": 64, "input_width": 64,
                          "normalize_mean": [0.485, 0.456, 0.406], "normalize_std": [0.229, 0.224, 0.225]},
        "model": {"encoder_name": "resnet18", "decoder_channels": DECODER},
    }
    training_path = root / "training.json"
    training_path.write_text(json.dumps(training), encoding="utf-8")
    inference = {
        "inference_config_version": "test-v1",
        "model": {
            "model_version": "tiny-test-model",
            "experiment_id": "TEST",
            "checkpoint_path": str(checkpoint),
            "checkpoint_sha256": _sha256(checkpoint),
            "training_config_path": str(training_path),
        },
        "postprocessing": {"threshold": threshold, "min_component_area": min_area, "tta": True},
        "input": {"allowed_formats": ["PNG", "JPEG"], "max_pixels": 4_000_000},
        "runtime": {"device": "cpu", "determinism_policy": "test"},
    }
    config_path = root / "inference.json"
    config_path.write_text(json.dumps(inference), encoding="utf-8")
    return config_path


@pytest.fixture(autouse=True)
def database_url(tmp_path, monkeypatch):
    """A fresh database per test: SQLite by default, or an empty PostgreSQL
    schema when ``DFU_TEST_DATABASE_URL`` is set, so the suite runs on both."""

    server = os.environ.get("DFU_TEST_DATABASE_URL")
    if not server:
        yield str(tmp_path / "test.sqlite3")
        return

    from sqlalchemy import text

    from src.storage.database import create_database_engine, migrate

    schema = f"test_{uuid.uuid4().hex}"
    url = f"{server}{'&' if '?' in server else '?'}options=-csearch_path%3D{schema}"
    admin = create_database_engine(server)
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    migrate(url)
    monkeypatch.setenv("DFU_DATABASE_URL", url)
    yield url
    with admin.begin() as connection:
        connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    admin.dispose()


@pytest.fixture(scope="session")
def s3_endpoint():
    """A real S3 API: MinIO when ``DFU_TEST_S3_ENDPOINT`` is set, else a local moto server."""

    endpoint = os.environ.get("DFU_TEST_S3_ENDPOINT")
    if endpoint:
        yield endpoint
        return

    from moto.server import ThreadedMotoServer

    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


@pytest.fixture
def s3_store(s3_endpoint, monkeypatch):
    """An empty private bucket per test."""

    for name, value in (("AWS_ACCESS_KEY_ID", "test-only"), ("AWS_SECRET_ACCESS_KEY", "test-only"),
                        ("AWS_DEFAULT_REGION", "us-east-1")):
        if not os.environ.get("DFU_TEST_S3_ENDPOINT"):
            monkeypatch.setenv(name, value)

    from src.storage.blobs import S3BlobStore

    store = S3BlobStore(f"test-{uuid.uuid4().hex}", s3_endpoint)
    store.client.create_bucket(Bucket=store.bucket)
    return store


class SignIn:
    """A fake sign-in provider: one RSA key, its JWKS document, and token minting."""

    issuer = "https://signin.test"
    audience = "dfu-tests"
    key_id = "test-key"

    def __init__(self) -> None:
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        from src.api.auth import JwksCache, TokenVerifier

        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key.public_key()))
        self.jwks = {"keys": [{**public, "kid": self.key_id, "use": "sig", "alg": "RS256"}]}
        self.verifier = TokenVerifier(self.issuer, self.audience, JwksCache("https://signin.test/jwks", lambda _: self.jwks))

    def token(self, subject: str | None = "user-a", *, key=None, algorithm: str = "RS256", kid: str | None = "test-key",
              without: tuple[str, ...] = (), **claims) -> str:
        import jwt

        now = int(time.time())
        body = {"iss": self.issuer, "aud": self.audience, "exp": now + 300, "iat": now, "sub": subject, **claims}
        return jwt.encode({name: value for name, value in body.items() if name not in without},
                          key if key is not None else self.private_key, algorithm=algorithm,
                          headers={"kid": kid} if kid else None)

    def headers(self, subject: str = "user-a") -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(subject)}"}

    def repository(self, state, subject: str = "user-a"):
        return state.db.for_owner(state.db.ensure_user(f"{self.issuer}|{subject}"))


@pytest.fixture(scope="session")
def auth() -> SignIn:
    return SignIn()


@pytest.fixture(scope="session")
def tiny_inference_config(tmp_path_factory) -> Path:
    return write_artifact(tmp_path_factory.mktemp("artifact"))


@pytest.fixture(scope="session")
def tiny_engine(tiny_inference_config):
    from src.inference.engine import InferenceEngine

    return InferenceEngine.from_config(tiny_inference_config)


def textured_png(path: Path, size=(96, 80), seed: int = 1) -> Path:
    """A sharp, well-exposed synthetic image that passes the quality gate."""

    rng = np.random.default_rng(seed)
    height, width = size[1], size[0]
    base = np.full((height, width, 3), (170, 120, 100), dtype=np.float32)
    noise = rng.normal(0, 30, (height, width, 3))
    yy, xx = np.mgrid[:height, :width]
    wound = ((yy - height / 2) ** 2 + (xx - width / 2) ** 2) < (min(height, width) / 4) ** 2
    base[wound] = (150, 40, 40)
    Image.fromarray(np.clip(base + noise, 0, 255).astype(np.uint8)).save(path)
    return path


@pytest.fixture
def make_image(tmp_path):
    """Factory fixture: ``make_image(name, size=(w, h), seed=1)`` -> path to a quality-passing PNG."""

    def factory(name: str = "image.png", size=(96, 80), seed: int = 1) -> Path:
        return textured_png(tmp_path / name, size=size, seed=seed)

    return factory
