"""Shared test setup: send agent logging to a temp file so test runs never write the real agent.log."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from orchestration.logger import AGENT_LOG_PATH_ENV_VAR

# Set at import, before any test can create the log handler.
os.environ[AGENT_LOG_PATH_ENV_VAR] = str(Path(tempfile.mkdtemp(prefix="agent_log_")) / "agent.log")
