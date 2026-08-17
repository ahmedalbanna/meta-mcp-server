"""Smoke tests: every registered tool returns a parseable JSON string when the
Meta SDK is fully mocked (no network). Exercises the whole register() surface.
"""

import importlib
import inspect
import json

from tests.conftest import Recorder, TOOL_MODULES, register_all


def _sample_args(fn):
    kwargs = {}
    for name, param in inspect.signature(fn).parameters.items():
        if param.default is not inspect.Parameter.empty:
            continue
        ann = param.annotation
        if ann is int:
            kwargs[name] = 1
        elif ann is float:
            kwargs[name] = 1.5
        elif ann is bool:
            kwargs[name] = True
        elif ann is dict:
            kwargs[name] = {}
        elif ann is list:
            kwargs[name] = []
        else:
            kwargs[name] = "test"
    return kwargs


def _all_tools(mock_meta_sdk):
    recorder = register_all(Recorder())
    return list(recorder.tools.items())


def test_all_tools_return_json_string(mock_meta_sdk):
    for name, fn in _all_tools(mock_meta_sdk):
        result = fn(**_sample_args(fn))
        assert isinstance(result, str), f"{name} did not return a string"
        parsed = json.loads(result)
        assert isinstance(parsed, (dict, list)), f"{name} returned non-JSON data"


def test_each_module_tools_callable(mock_meta_sdk):
    for module_name in TOOL_MODULES:
        module = importlib.import_module(f"src.{module_name}")
        recorder = Recorder()
        module.register(recorder)
        for name, fn in recorder.tools.items():
            result = fn(**_sample_args(fn))
            json.loads(result)
