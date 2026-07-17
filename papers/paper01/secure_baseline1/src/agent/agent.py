from __future__ import annotations

import argparse
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

from agent_funs import (
    load_pgroup,
    load_prompt,
    run_git_snapshot,
    run_program,
    send_pgroup,
    send_prompt,
    setup_logger,
)
from codex_runner import CodexRunner
from session_inspector import SessionInspection, inspect_sessions


ROOT = Path(__file__).resolve().parent
DEFAULT_AGENT_RUN_DIR = ROOT / "agent_run"
WORKSPACE_INIT_DIR = ROOT / "workspace_init"
PROMPT_DIR = ROOT / "prompts"
LOG_FILE = ROOT / "agent.log"


def resolve_log_file() -> Path:
    return LOG_FILE


def ensure_fresh_run_paths(run_dir: Path) -> None:
    if run_dir.exists():
        raise FileExistsError(f"Agent run directory already exists: {run_dir}")


def prepare_agent_run(run_dir: Path) -> None:
    shutil.copytree(WORKSPACE_INIT_DIR, run_dir)


def ensure_recovery_run_paths(run_dir: Path) -> None:
    missing_paths = [
        path
        for path in (
            run_dir,
            run_dir / "client",
            run_dir / "client" / "client.py",
            run_dir / "client" / "session",
            LOG_FILE,
        )
        if not path.exists()
    ]
    if missing_paths:
        missing_list = ", ".join(str(path) for path in missing_paths)
        raise FileNotFoundError(f"Recovery requires existing run paths: {missing_list}")


class SimpleAgent:
    def __init__(
        self,
        run_dir: str | Path,
        game_name: str | None = None,
        model: str = "gpt-5.5",
        reasoning_effort: str = "medium",
    ):
        self.run_dir = Path(run_dir)
        self.client_path = self.run_dir / "client" / "client.py"
        self.session_dir = self.run_dir / "client" / "session"
        self.log_file = resolve_log_file()
        self.game_name = game_name
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.logger = setup_logger(self.log_file)
        self.logger.info(
            "agent parameters",
            extra={
                "run_dir": str(self.run_dir.resolve()),
                "game_name": self.game_name,
                "model": self.model,
                "reasoning_effort": self.reasoning_effort,
            },
        )
        self.runner = CodexRunner(
            work_dir=self.run_dir,
            log_file=self.log_file,
            model=self.model,
            reasoning_effort=self.reasoning_effort,
        )
        self.iteration_id = 0
        self.previous_loop_level_index: int | None = None
        self.previous_loop_n_steps_total: int | None = None
        self.last_trouble1: defaultdict[int, int] = defaultdict(int)
        self.last_trouble2: defaultdict[int, int] = defaultdict(int)
        self.last_stuck_step: int | None = None

        self.main_prompt = load_prompt(PROMPT_DIR, "main_prompt.md", self.logger)
        self.continuation_string = load_prompt(
            PROMPT_DIR,
            "continuation_string.txt",
            self.logger,
        )
        self.hard_refactoring_pgroup = load_pgroup(
            PROMPT_DIR,
            self.logger,
            "world_engine_simplification*",
            "world_model_state_io_simplification*",
            "world_model_planner.txt",
        )
        self.level1_light_simplification_prompt = load_prompt(
            PROMPT_DIR,
            "light_simplification_level1.txt",
            self.logger,
        )
        self.level1_normal_continuation_prompt = load_prompt(
            PROMPT_DIR,
            "continuation_level1.txt",
            self.logger,
        )
        self.normal_continuation_prompt = load_prompt(
            PROMPT_DIR,
            "continuation_l2.txt",
            self.logger,
        )
        self.new_level_prompt = load_prompt(PROMPT_DIR, "on_new_level_v1.txt", self.logger)
        self.level1_trouble1_prompt = load_prompt(
            PROMPT_DIR,
            "trouble1_prompt_level1.txt",
            self.logger,
        )
        self.level1_trouble2_prompt = load_prompt(
            PROMPT_DIR,
            "trouble2_prompt_level1.txt",
            self.logger,
        )
        self.trouble1_prompt = load_prompt(PROMPT_DIR, "trouble1_prompt.txt", self.logger)
        self.trouble2_prompt = load_prompt(PROMPT_DIR, "trouble2_prompt.txt", self.logger)
        self.stuck_reminder_prompt = load_prompt(
            PROMPT_DIR,
            "stuck_reminder_prompt.txt",
            self.logger,
        )
        self.death_prompt = load_prompt(PROMPT_DIR, "death_prompt.txt", self.logger)
        self.recovery_prompt = load_prompt(PROMPT_DIR, "recovery_prompt.txt", self.logger)

    def init_iterations(self) -> None:
        if self.game_name is None:
            raise RuntimeError("game_name is required for master mode initialization.")

        game_init_screenout = self.run_client(f"start {self.game_name}")
        initial_prompt = (
            self.main_prompt
            + "\n\n"
            + self.continuation_string
            + "\n\nThe initial output of the game client:\n"
            + game_init_screenout
        )
        self.send_prompt(initial_prompt)

    def init_recovery(self) -> None:
        inspection = inspect_sessions(self.session_dir)
        self.logger.info("start init_recovery", extra=inspection.to_dict())

        if inspection.n_steps_total == 0:
            raise RuntimeError("Recovery requires at least one completed step.")

        if inspection.is_game_over:
            self.logger.info(
                "resetting game-over state during recovery",
                extra=inspection.to_dict(),
            )
            self.run_client("move RESET")
            inspection = inspect_sessions(self.session_dir)
            self.logger.info("post-reset recovery inspection", extra=inspection.to_dict())

        self.send_prompt(self.main_prompt + "\n\n" + self.recovery_prompt)
        self.normal_continuation_protocol(inspection)

    def run_git(self, inspection: SessionInspection) -> None:
        run_git_snapshot(
            agent_run_dir=self.run_dir,
            level_index=inspection.current_level_index,
            global_step_count=inspection.n_steps_total,
            iteration_count=self.iteration_id,
            logger=self.logger,
        )

    def run_client(self, command: str) -> str:
        return run_program(f"python3 {self.client_path} {command}", cwd=ROOT, logger=self.logger)

    def send_prompt(self, prompt: str) -> None:
        send_prompt(self.runner, prompt, self.logger)

    def send_pgroup(self, prompts: list[str]) -> None:
        send_pgroup(self.runner, prompts, self.logger)

    def stop_condition(self, inspection: SessionInspection) -> bool:
        if inspection.current_level_index is None:
            self.logger.info("stop condition met", extra={"reason": "no current level found"})
            return True
        if inspection.n_steps_current_level >= 1500:
            self.logger.info(
                "stop condition met",
                extra={"reason": "current level reached step limit"},
            )
            return True
        if self.last_stuck_step is not None and inspection.n_steps_total == self.last_stuck_step:
            self.logger.info(
                "stop condition met",
                extra={"reason": "no progress after stuck protocol"},
            )
            return True
        if inspection.is_solved:
            self.logger.info("stop condition met", extra={"reason": "game solved"})
            return True
        return False

    def get_simple_contination_prompt(self, inspection: SessionInspection) -> str:
        if inspection.current_level_index == 1:
            return self.level1_normal_continuation_prompt + "\n" + self.continuation_string
        return self.normal_continuation_prompt + "\n" + self.continuation_string

    def send_simplification_prompts(self, inspection: SessionInspection) -> None:
        if inspection.current_level_index == 1:
            self.send_prompt(self.level1_light_simplification_prompt)
        else:
            self.send_pgroup(self.hard_refactoring_pgroup)

    def normal_continuation_protocol(self, inspection: SessionInspection) -> None:
        self.logger.info("selected protocol", extra={"protocol": "normal_continuation_protocol"})
        self.send_simplification_prompts(inspection)
        self.send_prompt(self.get_simple_contination_prompt(inspection))

    def new_level_protocol(self, inspection: SessionInspection) -> None:
        self.logger.info("selected protocol", extra={"protocol": "new_level_protocol"})
        self.send_prompt(self.new_level_prompt)
        self.normal_continuation_protocol(inspection)

    def normal_reset_protocol(self, inspection: SessionInspection, reset_string: str) -> None:
        self.logger.info("selected protocol", extra={"protocol": "normal_reset_protocol"})
        contination_prompt = self.get_simple_contination_prompt(inspection)
        prompt = (
            contination_prompt
            + "\n\nThe level has been reset. You have another attempt. Output from the client:\n"
            + reset_string
        )
        self.send_prompt(prompt)

    def trouble_protocol1(self, inspection: SessionInspection, reset_string: str) -> None:
        self.logger.info("selected protocol", extra={"protocol": "trouble_protocol1"})
        if inspection.current_level_index == 1:
            prompt_prefix = self.level1_trouble1_prompt
        else:
            prompt_prefix = self.trouble1_prompt

        prompt = (
            prompt_prefix
            + "\n"
            + self.continuation_string
            + "\n\nThe level has been reset. You have another attempt. Output from the client:\n"
            + reset_string
        )
        self.send_prompt(prompt)

    def trouble_protocol2(self, inspection: SessionInspection, reset_string: str) -> None:
        self.logger.info("selected protocol", extra={"protocol": "trouble_protocol2"})
        self.runner.new_session()

        if inspection.current_level_index == 1:
            middle_prompt = self.level1_trouble2_prompt
        else:
            middle_prompt = self.trouble2_prompt

        prompt = (
            self.main_prompt
            + "\n\n"
            + self.continuation_string
            + "\n\n"
            + middle_prompt
            + "\n"
            + self.continuation_string
            + "\n\nThe level has been reset. You have another attempt. Output from the client:\n"
            + reset_string
        )
        self.send_prompt(prompt)

    def reset_protocol(self, inspection: SessionInspection) -> None:
        self.logger.info("selected protocol", extra={"protocol": "reset_protocol"})
        if inspection.is_game_over:
            self.send_prompt(self.death_prompt)
        self.send_simplification_prompts(inspection)
        reset_string = self.run_client("move RESET")

        steps = inspection.n_steps_current_level
        level = inspection.current_level_index
        if level is None:
            raise RuntimeError("Current level is unknown during reset protocol.")

        if steps > self.last_trouble2[level] + 200:
            self.last_trouble2[level] = steps
            self.last_trouble1[level] = steps
            self.trouble_protocol2(inspection, reset_string)
        elif steps > self.last_trouble1[level] + 100:
            self.last_trouble1[level] = steps
            self.trouble_protocol1(inspection, reset_string)
        else:
            self.normal_reset_protocol(inspection, reset_string)

    def stuck_protocol(self, inspection: SessionInspection) -> None:
        self.logger.info("selected protocol", extra={"protocol": "stuck_protocol"})
        self.send_simplification_prompts(inspection)
        prompt = self.get_simple_contination_prompt(inspection) + "\n" + self.stuck_reminder_prompt
        self.send_prompt(prompt)

    def iteration_loop(self, inspection: SessionInspection) -> None:
        self.run_git(inspection)

        if inspection.is_game_over:
            self.reset_protocol(inspection)
        elif inspection.current_level_index != 1 and inspection.current_level_index != self.previous_loop_level_index:
            self.new_level_protocol(inspection)
        elif self.previous_loop_n_steps_total == inspection.n_steps_total:
            self.stuck_protocol(inspection)
            self.last_stuck_step = inspection.n_steps_total
        else:
            self.normal_continuation_protocol(inspection)

        self.previous_loop_level_index = inspection.current_level_index
        self.previous_loop_n_steps_total = inspection.n_steps_total

    def run(self, recovery: bool = False) -> int:
        self.logger.info(
            "starting agent",
            extra={
                "game_name": self.game_name,
                "run_dir": str(self.run_dir.resolve()),
                "recovery": recovery,
                "model": self.model,
                "reasoning_effort": self.reasoning_effort,
            },
        )

        try:
            if recovery:
                self.init_recovery()
            else:
                self.init_iterations()
        except Exception:
            self.logger.exception("initialization failed")
            return 1

        while True:
            self.iteration_id += 1
            try:
                inspection = inspect_sessions(self.session_dir)
            except Exception:
                self.logger.exception("failed to inspect sessions", extra={"iteration_id": self.iteration_id})
                return 1

            self.logger.info(
                "iteration inspection",
                extra={
                    "iteration_id": self.iteration_id,
                    **inspection.to_dict(),
                },
            )

            if self.stop_condition(inspection):
                self.logger.info("stopping main loop", extra={"iteration_id": self.iteration_id})
                return 0

            try:
                self.iteration_loop(inspection)
            except Exception:
                self.logger.exception("iteration loop failed", extra={"iteration_id": self.iteration_id})
                return 1

            time.sleep(1.0)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the simple agent.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--master", metavar="GAME_NAME")
    group.add_argument("--recovery", action="store_true")
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--reasoning-effort", default="medium")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    run_dir = DEFAULT_AGENT_RUN_DIR
    if args.master is not None:
        ensure_fresh_run_paths(run_dir)
        prepare_agent_run(run_dir)
        agent = SimpleAgent(
            run_dir=run_dir,
            game_name=args.master,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        return agent.run()

    ensure_recovery_run_paths(run_dir)
    agent = SimpleAgent(
        run_dir=run_dir,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
    )
    return agent.run(recovery=True)


if __name__ == "__main__":
    raise SystemExit(main())
