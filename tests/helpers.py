"""Build small throw-away projects for the tests."""
import json
import tempfile
from pathlib import Path


class Project:
    def __init__(self, files=None):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for rel, content in (files or {}).items():
            self.write(rel, content)

    def write(self, rel, content=""):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, (dict, list)):
            content = json.dumps(content)
        path.write_text(content, encoding="utf-8")
        return path

    def cleanup(self):
        self._tmp.cleanup()
