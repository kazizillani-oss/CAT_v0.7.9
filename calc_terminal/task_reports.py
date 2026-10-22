"""
CCT — task_reports.py: Structured Task Completion Reports (v0.7.10 spec #25).

Provides structured reports when tasks complete, including:
- Files changed
- Tests run/pass/fail
- Build status
- Preview status
- Todo progress
- Duration
- Any errors encountered

These reports are shown in the chat as structured completion cards.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class TaskStatus(Enum):
    """Status of a completed task."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    """Type of task that was completed."""
    BUILD = "build"
    TEST = "test"
    DEPLOY = "deploy"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"
    PACKAGE_INSTALL = "package_install"
    AI_GENERATION = "ai_generation"
    CUSTOM = "custom"


@dataclass
class FileChange:
    """A file that was changed during the task."""
    path: str
    change_type: str  # "created", "modified", "deleted"
    lines_added: int = 0
    lines_removed: int = 0


@dataclass
class TestResult:
    """Result of running tests."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration: float = 0.0
    test_file: str = ""
    error_message: str = ""


@dataclass
class BuildResult:
    """Result of a build operation."""
    success: bool = False
    duration: float = 0.0
    output: str = ""
    error: str = ""
    warnings: int = 0


@dataclass
class TaskReport:
    """A structured report of a completed task."""
    task_type: TaskType = TaskType.CUSTOM
    status: TaskStatus = TaskStatus.SUCCESS
    title: str = ""
    description: str = ""

    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    duration: float = 0.0

    # Changes
    files_changed: List[FileChange] = field(default_factory=list)

    # Build/Test results
    build_result: Optional[BuildResult] = None
    test_result: Optional[TestResult] = None

    # Preview
    preview_url: str = ""
    preview_active: bool = False

    # Todo progress
    todos_completed: int = 0
    todos_total: int = 0

    # Errors
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Additional context
    metadata: Dict[str, Any] = field(default_factory=dict)

    def complete(self, status: TaskStatus = TaskStatus.SUCCESS):
        """Mark the task as complete."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.status = status

    def add_file_change(self, path: str, change_type: str,
                        lines_added: int = 0, lines_removed: int = 0):
        """Add a file change to the report."""
        self.files_changed.append(FileChange(
            path=path,
            change_type=change_type,
            lines_added=lines_added,
            lines_removed=lines_removed
        ))

    def add_error(self, error: str):
        """Add an error to the report."""
        self.errors.append(error)
        if self.status == TaskStatus.SUCCESS:
            self.status = TaskStatus.PARTIAL

    def add_warning(self, warning: str):
        """Add a warning to the report."""
        self.warnings.append(warning)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "task_type": self.task_type.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "duration": self.duration,
            "files_changed": [
                {
                    "path": fc.path,
                    "change_type": fc.change_type,
                    "lines_added": fc.lines_added,
                    "lines_removed": fc.lines_removed,
                }
                for fc in self.files_changed
            ],
            "build_result": {
                "success": self.build_result.success,
                "duration": self.build_result.duration,
                "warnings": self.build_result.warnings,
            } if self.build_result else None,
            "test_result": {
                "total": self.test_result.total,
                "passed": self.test_result.passed,
                "failed": self.test_result.failed,
                "duration": self.test_result.duration,
            } if self.test_result else None,
            "preview_url": self.preview_url,
            "preview_active": self.preview_active,
            "todos_completed": self.todos_completed,
            "todos_total": self.todos_total,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def to_markdown(self) -> str:
        """Convert report to markdown for chat display."""
        lines = []

        # Status icon
        status_icons = {
            TaskStatus.SUCCESS: "✓",
            TaskStatus.PARTIAL: "⚠",
            TaskStatus.FAILED: "✗",
            TaskStatus.CANCELLED: "⊘",
        }
        icon = status_icons.get(self.status, "?")

        # Title
        lines.append(f"### {icon} {self.title}")
        if self.description:
            lines.append(f"{self.description}")
        lines.append("")

        # Duration
        if self.duration > 0:
            lines.append(f"**Duration:** {self.duration:.1f}s")

        # Files changed
        if self.files_changed:
            lines.append(f"**Files changed:** {len(self.files_changed)}")
            for fc in self.files_changed[:5]:  # Limit to 5 files
                lines.append(f"- `{fc.path}` ({fc.change_type})")
            if len(self.files_changed) > 5:
                lines.append(f"- ... and {len(self.files_changed) - 5} more")

        # Build result
        if self.build_result:
            status = "✓ passed" if self.build_result.success else "✗ failed"
            lines.append(f"**Build:** {status} ({self.build_result.duration:.1f}s)")
            if self.build_result.warnings:
                lines.append(f"**Warnings:** {self.build_result.warnings}")

        # Test result
        if self.test_result:
            lines.append(
                f"**Tests:** {self.test_result.passed}/{self.test_result.total} passed"
            )
            if self.test_result.failed:
                lines.append(f"**Failed:** {self.test_result.failed}")

        # Preview
        if self.preview_url:
            lines.append(f"**Preview:** {self.preview_url}")

        # Todo progress
        if self.todos_total > 0:
            lines.append(
                f"**Todos:** {self.todos_completed}/{self.todos_total} completed"
            )

        # Errors
        if self.errors:
            lines.append("")
            lines.append("**Errors:**")
            for error in self.errors[:3]:
                lines.append(f"- {error}")

        # Warnings
        if self.warnings:
            lines.append("")
            lines.append("**Warnings:**")
            for warning in self.warnings[:3]:
                lines.append(f"- {warning}")

        return "\n".join(lines)


class TaskReportManager:
    """Manages task completion reports."""

    def __init__(self):
        self._reports = []
        self._max_reports = 100

    def create_report(self, task_type: TaskType, title: str,
                      description: str = "") -> TaskReport:
        """Create a new task report."""
        report = TaskReport(
            task_type=task_type,
            title=title,
            description=description,
        )
        self._reports.append(report)
        if len(self._reports) > self._max_reports:
            self._reports = self._reports[-self._max_reports:]
        return report

    def get_recent_reports(self, count: int = 10) -> List[TaskReport]:
        """Get recent task reports."""
        return self._reports[-count:]

    def get_reports_by_type(self, task_type: TaskType) -> List[TaskReport]:
        """Get reports filtered by task type."""
        return [r for r in self._reports if r.task_type == task_type]


# Global instance
_task_report_manager = None


def get_task_report_manager() -> TaskReportManager:
    """Get or create the global task report manager."""
    global _task_report_manager
    if _task_report_manager is None:
        _task_report_manager = TaskReportManager()
    return _task_report_manager
