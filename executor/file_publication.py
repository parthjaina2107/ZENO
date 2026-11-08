"""Publish completed local files without replacing a competing destination."""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


def publish_new(staged, target):
    if os.name == "nt":
        os.rename(staged, target)  # Windows rename refuses an existing destination.
    else:
        os.link(staged, target)


@contextmanager
def stage_new_file(target):
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".zeno-", delete=False) as stream:
        staged = Path(stream.name)
    try:
        yield staged
        publish_new(staged, target)
    finally:
        staged.unlink(missing_ok=True)
