"""Das Installationsskript darf fremde Hooks nie anfassen und muss idempotent sein."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("install_script", ROOT / "scripts" / "install.py")
install = importlib.util.module_from_spec(spec)
sys.modules["install_script"] = install
spec.loader.exec_module(install)

FOREIGN = {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo fremd"}]}


def rendered(port=8765, token="tok"):
    template = json.loads((ROOT / "hooks" / "settings-hooks.json").read_text(encoding="utf-8"))
    return install.render_hooks(template, python="C:/py/python.exe", port=port, token=token)


def test_template_is_valid_and_fully_rendered():
    hooks = rendered()
    text = json.dumps(hooks)
    assert "{{" not in text and "_comment" not in hooks
    assert set(hooks) == {"UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStart", "SubagentStop", "SessionEnd"}
    assert "Bearer tok" in text and "127.0.0.1:8765" in text


def test_agent_gate_is_a_command_hook_with_exec_form():
    gate = next(h for e in rendered()["PreToolUse"] if e.get("matcher") == "Agent" for h in e["hooks"])
    assert gate["type"] == "command" and gate["command"] == "C:/py/python.exe" and gate["args"] == ["-m", "team_manager.agent_gate"]


def test_merge_keeps_foreign_hooks_and_settings():
    settings = {"model": "opus", "hooks": {"PreToolUse": [FOREIGN], "Stop": [FOREIGN]}}
    merged = install.merge_hooks(settings, rendered())
    assert merged["model"] == "opus"
    assert FOREIGN in merged["hooks"]["PreToolUse"] and merged["hooks"]["Stop"] == [FOREIGN]
    assert any(install.is_ours(e) for e in merged["hooks"]["PreToolUse"])
    assert settings["hooks"]["PreToolUse"] == [FOREIGN]  # Eingabe unverändert


def test_merge_is_idempotent_and_replaces_old_port_and_token():
    once = install.merge_hooks({}, rendered(8765, "alt"))
    twice = install.merge_hooks(once, rendered(8765, "alt"))
    assert once == twice
    moved = install.merge_hooks(once, rendered(9000, "neu"))
    text = json.dumps(moved)
    assert "8765" not in text and "alt" not in text and "9000" in text and "neu" in text


def test_remove_restores_original():
    original = {"model": "opus", "hooks": {"PreToolUse": [FOREIGN]}}
    assert install.remove_hooks(install.merge_hooks(original, rendered())) == original


def test_remove_cleans_empty_hooks_block():
    assert install.remove_hooks(install.merge_hooks({"model": "x"}, rendered())) == {"model": "x"}


def test_is_ours_ignores_foreign_http_hooks():
    foreign_http = {"hooks": [{"type": "http", "url": "https://example.com/hooks"}]}
    other_local = {"hooks": [{"type": "http", "url": "http://127.0.0.1:9999/collect"}]}
    assert not install.is_ours(foreign_http) and not install.is_ours(other_local)
