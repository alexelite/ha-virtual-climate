#!/usr/bin/env python3
"""Package locally or deploy over SSH. Rollback restores code, never HA storage."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

DOMAIN = "virtual_climate"
IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def included(path):
    return not (set(path.parts) & IGNORED_DIRS or path.name == ".DS_Store" or path.suffix in {".pyc", ".pyo"})


def payload_manifest(folder):
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest.get("domain") != DOMAIN or not manifest.get("version"):
        raise RuntimeError("Expected a versioned virtual_climate component")
    files = {}
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder)
        if not included(relative):
            continue
        if path.is_symlink():
            raise RuntimeError(f"Component symlinks are not supported: {relative}")
        if path.is_file():
            files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"version": manifest["version"], "sha256": digest, "files": files}


def copy_component(source, destination):
    payload_manifest(source)
    shutil.copytree(source, destination, ignore=lambda directory, names: [
        name for name in names if not included(Path(name))
    ])


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2)
        stream.write("\n")
    temporary.replace(path)


def run(command):
    return subprocess.run(command, text=True, capture_output=True, timeout=180)


def inspect_host(config_root=None):
    candidates = [Path(config_root)] if config_root else [
        Path("/config"), Path("/mnt/data/supervisor/homeassistant"), Path("/usr/share/hassio/homeassistant"),
    ]
    for root in candidates:
        target = root / "custom_components" / DOMAIN
        if (target / "manifest.json").is_file():
            installed = payload_manifest(target)
            if not shutil.which("docker") or not shutil.which("ha"):
                raise RuntimeError("Deployment requires docker and the HA CLI on the SSH host")
            result = run(["docker", "inspect", "--format", "{{.State.Status}}", "homeassistant"])
            if result.returncode or result.stdout.strip() != "running":
                raise RuntimeError("The homeassistant container must be running before deployment")
            return {"config_root": str(root), "target": str(target), "version": installed["version"], "sha256": installed["sha256"]}
    raise RuntimeError("Cannot find the installed component; set --config-root explicitly")


class Deployment:
    def __init__(self, config_root, run_id):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", run_id) or ".." in run_id:
            raise ValueError("Invalid deployment/backup id")
        self.root = Path(config_root)
        self.target = self.root / "custom_components" / DOMAIN
        self.backups = self.root / "virtual_climate_backups"
        self.folder = self.backups / run_id
        self.lock = self.backups / ".deploy-lock"
        self.run_id = run_id
        self.stage_parent = self.folder / "stage"
        self.stage = self.stage_parent / "custom_components" / DOMAIN
        self.state_path = self.folder / "deployment.json"

    def state(self):
        return json.loads(self.state_path.read_text())

    def update(self, **values):
        data = self.state()
        data.update(values)
        write_json(self.state_path, data)
        return data

    def assert_owner(self):
        if not self.lock.is_file() or self.lock.read_text().strip() != self.run_id:
            raise RuntimeError("Deployment lock is missing or belongs to another run")

    def release(self):
        if self.lock.is_file() and self.lock.read_text().strip() == self.run_id:
            self.lock.unlink()

    def prepare(self, from_backup=None):
        if self.target.is_symlink():
            raise RuntimeError("Refusing to replace a symlinked component directory")
        original = payload_manifest(self.target)
        self.backups.mkdir(mode=0o700, exist_ok=True)
        try:
            with self.lock.open("x") as stream:
                stream.write(self.run_id + "\n")
        except FileExistsError:
            raise RuntimeError("Another deployment owns virtual_climate_backups/.deploy-lock") from None
        try:
            self.folder.mkdir(mode=0o700)
            copy_component(self.target, self.folder / "component")
            # Read only this integration's persisted entries for reference/rollback.
            # Config restore is always through HA APIs; this file is never written back.
            entries_path = self.root / ".storage" / "core.config_entries"
            entries = json.loads(entries_path.read_text())["data"]["entries"]
            selected = [entry for entry in entries if entry.get("domain") == DOMAIN]
            if not selected:
                raise RuntimeError("No virtual_climate config entry found for the pre-deploy snapshot")
            write_json(self.folder / "config-entries.json", {
                "domain": DOMAIN, "entries": selected,
                "note": "Reference snapshot only. Restore settings through HA APIs, never by replacing .storage.",
            })
            self.stage.parent.mkdir(parents=True)
            write_json(self.state_path, {
                "backup_id": self.run_id, "status": "prepared", "old_payload": original,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            if from_backup:
                previous = Deployment(self.root, from_backup)
                copy_component(previous.folder / "component", self.stage)
                write_json(self.folder / "payload.json", payload_manifest(self.stage))
            return {"backup_id": self.run_id, "backup_path": str(self.folder),
                    "stage": str(self.stage), "payload_path": str(self.folder / "payload.json")}
        except BaseException:
            self.release()
            raise

    def verify_stage(self):
        self.assert_owner()
        expected = json.loads((self.folder / "payload.json").read_text())
        actual = payload_manifest(self.stage)
        if actual["files"] != expected["files"] or actual["sha256"] != expected["sha256"]:
            raise RuntimeError("Transferred component does not match the local SHA-256 manifest")
        for path in self.stage.rglob("*.py"):
            if included(path.relative_to(self.stage)):
                ast.parse(path.read_text(), filename=str(path))
        for path in self.stage.rglob("*.json"):
            json.loads(path.read_text())
        self.verify_runtime_imports()
        return self.update(status="verified", new_payload=actual)

    def verify_runtime_imports(self):
        container_parent = "/config/" + self.stage_parent.relative_to(self.root).as_posix()
        probe = """
import asyncio, importlib, pathlib, sys
async def main():
    sys.path.insert(0, sys.argv[1])
    import custom_components
    custom_components.__path__ = [str(pathlib.Path(sys.argv[1]) / 'custom_components')]
    for suffix in ('', '.config_flow', '.zone_manager', '.climate', '.sensor', '.binary_sensor'):
        module = importlib.import_module('custom_components.virtual_climate' + suffix)
        if not pathlib.Path(module.__file__).is_relative_to(pathlib.Path(sys.argv[1])):
            raise RuntimeError('Import probe loaded a different component copy')
    import yaml
    yaml.safe_load((pathlib.Path(sys.argv[1]) / 'custom_components/virtual_climate/services.yaml').read_text())
asyncio.run(main())
"""
        result = run(["docker", "exec", "homeassistant", "python", "-c", probe, container_parent])
        if result.returncode:
            self.save_log("import-check.log", result)
            raise RuntimeError(f"Import check failed inside the real HA runtime; see {self.folder}/import-check.log")

    def save_log(self, filename, result):
        path = self.folder / filename
        path.write_text(result.stdout + "\n" + result.stderr)
        path.chmod(0o600)

    def check_config(self):
        result = run(["ha", "core", "check"])
        self.save_log("config-check.log", result)
        if result.returncode:
            raise RuntimeError(f"HA configuration check failed; see {self.folder}/config-check.log")

    def restart_and_wait(self):
        before = run(["docker", "inspect", "--format", "{{.State.StartedAt}}", "homeassistant"]).stdout.strip()
        info = run(["ha", "core", "info", "--raw-json"])
        data = json.loads(info.stdout).get("data", {}) if info.returncode == 0 else {}
        url = f"{'https' if data.get('ssl') else 'http'}://127.0.0.1:{data.get('port', 8123)}/api/"
        try:
            result = run(["ha", "core", "restart"])
        except subprocess.TimeoutExpired:
            result = subprocess.CompletedProcess(["ha", "core", "restart"], 1, "", "HA CLI timed out; checking process/API readiness")
        self.save_log("restart.log", result)
        # A CLI timeout is ambiguous: check the new Core process and API explicitly.
        deadline = time.monotonic() + 240
        probe = """
import ssl, sys, urllib.error, urllib.request
try:
    response = urllib.request.urlopen(sys.argv[1], timeout=3, context=ssl._create_unverified_context())
    code = response.status
except urllib.error.HTTPError as error:
    code = error.code
sys.exit(0 if code in (200, 401) else 1)
"""
        while time.monotonic() < deadline:
            status = run(["docker", "inspect", "--format", "{{json .State}}", "homeassistant"])
            if status.returncode == 0:
                state = json.loads(status.stdout)
                if state.get("Status") == "running" and state.get("StartedAt") != before:
                    ready = run(["docker", "exec", "homeassistant", "python", "-c", probe, url])
                    if ready.returncode == 0:
                        return
            time.sleep(3)
        raise RuntimeError("A restarted HA API did not become ready within 240 seconds")

    def restore_code(self):
        original = self.folder / "original-live"
        if not original.is_dir():
            raise RuntimeError("Cannot find the original component for rollback")
        self.target.rename(self.folder / "failed-component")
        original.rename(self.target)

    def activate(self, restart=True):
        self.assert_owner()
        if self.state()["status"] != "verified":
            raise RuntimeError("Stage must pass hash, syntax and real-runtime import checks first")
        if payload_manifest(self.target)["sha256"] != self.state()["old_payload"]["sha256"]:
            raise RuntimeError("Installed code changed while deployment was being prepared")
        if payload_manifest(self.stage)["sha256"] != self.state()["new_payload"]["sha256"]:
            raise RuntimeError("Verified stage was modified before activation")
        activated = False
        restart_attempted = False
        try:
            self.target.rename(self.folder / "original-live")
            try:
                self.stage.rename(self.target)
            except BaseException:
                (self.folder / "original-live").rename(self.target)
                raise
            activated = True
            self.update(status="activating")
            self.check_config()
            if restart:
                restart_attempted = True
                self.restart_and_wait()
            return self.update(status="installed" if restart else "pending_restart", restart_confirmed=restart)
        except BaseException as error:
            if activated:
                self.restore_code()
                self.update(status="rolled_back", failure=str(error))
                if restart_attempted:
                    try:
                        self.restart_and_wait()
                    except Exception as recovery_error:
                        self.update(status="rollback_needs_attention", recovery_failure=str(recovery_error))
                        raise RuntimeError(f"Previous code restored, but HA restart needs attention; backup={self.folder}") from recovery_error
            raise
        finally:
            self.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("build", "assert-source", "inspect", "prepare", "verify", "activate", "abort"))
    for name in ("source", "destination", "payload", "config-root", "run-id", "from-backup"):
        parser.add_argument("--" + name)
    parser.add_argument("--no-restart", action="store_true")
    args = parser.parse_args()
    if args.operation == "build":
        copy_component(Path(args.source), Path(args.destination))
        data = payload_manifest(args.destination)
        write_json(args.payload, data)
        print(json.dumps({"version": data["version"], "sha256": data["sha256"]}))
    elif args.operation == "assert-source":
        expected = json.loads(Path(args.payload).read_text())
        if payload_manifest(args.source)["sha256"] != expected["sha256"]:
            raise RuntimeError("Local component changed after packaging/testing; rerun deployment")
    elif args.operation == "inspect":
        print(json.dumps(inspect_host(args.config_root)))
    else:
        deploy = Deployment(args.config_root, args.run_id)
        if args.operation == "prepare":
            result = deploy.prepare(args.from_backup)
        elif args.operation == "verify":
            state = deploy.verify_stage()
            result = {"status": state["status"], "version": state["new_payload"]["version"], "sha256": state["new_payload"]["sha256"]}
        elif args.operation == "activate":
            state = deploy.activate(not args.no_restart)
            result = {"status": state["status"], "backup_id": deploy.run_id, "backup_path": str(deploy.folder),
                      "version": state["new_payload"]["version"], "sha256": state["new_payload"]["sha256"],
                      "restart_confirmed": state["restart_confirmed"]}
        else:
            deploy.release()
            result = {"status": "lock_released", "backup_id": deploy.run_id}
        print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Deployment failed: {error}", file=sys.stderr)
        raise SystemExit(1)
