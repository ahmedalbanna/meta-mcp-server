"""Tests for src/media_tools — local media listing and hosting wrappers."""

import json
from unittest import mock

from src import media_tools
from tests.conftest import Recorder


def test_list_local_media_returns_files(tmp_path):
    recorder = Recorder()
    media_tools.register(recorder)
    # set up a small media tree
    root = tmp_path / "media"
    root.mkdir()
    (root / "a.jpg").write_bytes(b"x" * 100)
    (root / "b.mp4").write_bytes(b"y" * 1000)
    (root / "ignore.txt").write_text("no")
    with mock.patch.object(media_tools, "MEDIA_ROOT", root):
        out = json.loads(recorder.tools["list_local_media"](subdir="", extensions=".jpg,.mp4"))
    assert out["count"] == 2
    names = {f["name"] for f in out["files"]}
    assert names == {"a.jpg", "b.mp4"}
    assert all("ignore.txt" not in f["name"] for f in out["files"])


def test_list_local_media_rejects_path_traversal(tmp_path):
    recorder = Recorder()
    media_tools.register(recorder)
    root = tmp_path / "media"
    root.mkdir()
    with mock.patch.object(media_tools, "MEDIA_ROOT", root):
        out = json.loads(recorder.tools["list_local_media"](subdir="../etc"))
    assert "error" in out


def test_host_image_url_requires_path():
    recorder = Recorder()
    media_tools.register(recorder)
    out = json.loads(recorder.tools["host_image_url"](file_path=""))
    assert "error" in out


def test_module_registers_tools_resources_prompts():
    recorder = Recorder()
    media_tools.register(recorder)
    assert set(recorder.tools) == {"host_image_url", "host_video_url", "host_many_images", "list_local_media"}
    assert len(recorder.resources) >= 2
    assert len(recorder.prompts) >= 2
