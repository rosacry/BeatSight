#!/usr/bin/env python3
"""Optional rich-enabled console helpers for BeatSight CLI utilities."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

_HAS_RICH = False
try:  # Optional dependency; fall back gracefully when unavailable.
    from rich.console import Console
    from rich.progress import (  # type: ignore[import]
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )

    _HAS_RICH = True
except ImportError:  # pragma: no cover - optional enhancement only
    Console = None  # type: ignore[assignment]
    Progress = None  # type: ignore[assignment]
    BarColumn = None  # type: ignore[assignment]
    MofNCompleteColumn = None  # type: ignore[assignment]
    SpinnerColumn = None  # type: ignore[assignment]
    TextColumn = None  # type: ignore[assignment]
    TimeElapsedColumn = None  # type: ignore[assignment]
    TimeRemainingColumn = None  # type: ignore[assignment]

HAS_RICH = _HAS_RICH

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from rich.console import Console as RichConsole  # type: ignore[import]
else:  # pragma: no cover - at runtime we only need duck typing
    RichConsole = Any  # type: ignore[assignment]


class OutputLogger:
    """Basic console wrapper that optionally mirrors output to a log file."""

    def __init__(
        self,
        *,
        enable_rich: bool = True,
        log_file: Optional[Path] = None,
        force_terminal: bool = False,
    ) -> None:
        self.enable_rich = bool(enable_rich and HAS_RICH)
        self.console: Optional[RichConsole] = (
            Console(force_terminal=force_terminal) if self.enable_rich and Console else None
        )

        self._log_handle = None
        self._log_console = None
        if log_file is not None:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = log_path.open("w", encoding="utf-8")
            if self.enable_rich and Console:
                self._log_console = Console(
                    file=self._log_handle,
                    force_terminal=False,
                    no_color=True,
                )

    @property
    def rich_console(self) -> Optional[RichConsole]:
        return self.console

    def print(self, *objects: Any, **kwargs: Any) -> None:
        if self.console is not None:
            self.console.print(*objects, **kwargs)
        else:
            print(*objects, **kwargs)

        if self._log_console is not None:
            self._log_console.print(*objects, **kwargs)
        elif self._log_handle is not None:
            sep = kwargs.get("sep", " ")
            end = kwargs.get("end", "\n")
            text = sep.join(str(obj) for obj in objects)
            self._log_handle.write(text + end)
            self._log_handle.flush()

    def status(self, message: str):
        if self.console is not None:
            return self.console.status(message)
        self.print(message)
        return nullcontext()

    def rule(self, title: Optional[str] = None) -> None:
        if self.console is not None:
            self.console.rule(title)
            if self._log_console is not None:
                self._log_console.rule(title)
            return

        line = "-" * 80
        if title:
            text = f" {title} "
            idx = max((len(line) - len(text)) // 2, 0)
            line = f"{line[:idx]}{text}{line[idx + len(text):]}"
        self.print(line)

    def close(self) -> None:
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None
            self._log_console = None

    def __enter__(self) -> "OutputLogger":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False


class ProgressAdapter:
    """Context manager that exposes a lightweight progress updater."""

    def __init__(
        self,
        logger: OutputLogger,
        description: str,
        *,
        total: Optional[int] = None,
        fields: Optional[Dict[str, Any]] = None,
        transient: bool = False,
    ) -> None:
        self._logger = logger
        self._description = description
        self._total = total
        self._fields = dict(fields or {})
        self._transient = transient
        self._progress = None
        self._task_id = None

    def __enter__(self) -> "ProgressAdapter":
        if self._logger.enable_rich and self._logger.rich_console is not None and Progress is not None:
            columns = [SpinnerColumn(), TextColumn("[progress.description]{task.description}")]
            if self._total is not None and BarColumn is not None and MofNCompleteColumn is not None:
                columns.append(BarColumn())
                columns.append(MofNCompleteColumn())
            else:
                columns.append(TextColumn("{task.completed:,} processed"))

            for key in self._fields:
                label = key.replace("_", " ").title()
                columns.append(TextColumn(f"{label}: {{task.fields[{key}]}}", justify="right"))

            if TimeElapsedColumn is not None:
                columns.append(TimeElapsedColumn())
            if self._total is not None and TimeRemainingColumn is not None:
                columns.append(TimeRemainingColumn())

            self._progress = Progress(*columns, console=self._logger.rich_console, transient=self._transient)
            self._progress.__enter__()
            self._task_id = self._progress.add_task(
                self._description,
                total=self._total,
                **self._fields,
            )
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._progress is not None:
            self._progress.__exit__(exc_type, exc, tb)
        return False

    @property
    def enabled(self) -> bool:
        return self._progress is not None and self._task_id is not None

    def update(self, *, advance: float = 0.0, **fields: Any) -> None:
        if not self.enabled or self._progress is None or self._task_id is None:
            return
        self._progress.update(self._task_id, advance=advance, **fields)


__all__ = ["HAS_RICH", "OutputLogger", "ProgressAdapter"]
