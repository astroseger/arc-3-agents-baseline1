#!/usr/bin/env python3

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class CodexRunner:
    def __init__(
        self,
        work_dir: str | Path,
        log_file: str | Path,
        model: str = "gpt-5.5",
        reasoning_effort: str = "medium",
        error_handling_manual: bool = False,
    ):
        self.work_dir = Path(work_dir)
        self.log_file = Path(log_file)
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.error_handling_manual = error_handling_manual
        self.current_thread_id: str | None = None

    def new_session(self) -> None:
        self.current_thread_id = None

    def send(self, prompt: str) -> list[dict[str, Any]]:
        if self.current_thread_id is None:
            events = self._run_command(
                [
                    "codex",
                    "-m",
                    self.model,
                    "-c",
                    f"model_reasoning_effort={self.reasoning_effort}",
                    "--dangerously-bypass-approvals-and-sandbox",
                    "exec",
                    "--cd",
                    str(self.work_dir),
                    "--json",
                ],
                prompt,
            )
            self.current_thread_id = self._find_thread_id(events)
            return events

        return self._run_command(
            [
                "codex",
                "-m",
                self.model,
                "-c",
                f"model_reasoning_effort={self.reasoning_effort}",
                "--dangerously-bypass-approvals-and-sandbox",
                "exec",
                "--cd",
                str(self.work_dir),
                "resume",
                self.current_thread_id,
                "--json",
            ],
            prompt,
        )

    def _run_command(self, command: list[str], prompt: str) -> list[dict[str, Any]]:
        while True:
            try:
                return self._run_command_once(command, prompt)
            except subprocess.CalledProcessError:
                if not self.error_handling_manual:
                    raise

                sys.stdout.write("ERROR IN CODEX. PRESS ENTER TO RETRY.\n")
                sys.stdout.flush()
                try:
                    input()
                except EOFError:
                    raise

    def _run_command_once(self, command: list[str], prompt: str) -> list[dict[str, Any]]:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
        )

        assert process.stdin is not None
        assert process.stdout is not None

        process.stdin.write(prompt)
        process.stdin.close()

        events: list[dict[str, Any]] = []
        with self.log_file.open("a", encoding="utf-8") as log_fh:
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log_fh.write(line)
                log_fh.flush()
                stripped = line.strip()
                if not stripped:
                    continue

                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    continue

                if isinstance(payload, dict):
                    events.append(payload)

        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)

        return events

    def _find_thread_id(self, events: list[dict[str, Any]]) -> str | None:
        for event in events:
            thread_id = self._extract_thread_id(event)
            if thread_id:
                return thread_id
        return None

    def _extract_thread_id(self, payload: Any) -> str | None:
        if isinstance(payload, dict):
            thread_id = payload.get("thread_id")
            if isinstance(thread_id, str):
                return thread_id

            for value in payload.values():
                thread_id = self._extract_thread_id(value)
                if thread_id:
                    return thread_id

        if isinstance(payload, list):
            for value in payload:
                thread_id = self._extract_thread_id(value)
                if thread_id:
                    return thread_id

        return None
