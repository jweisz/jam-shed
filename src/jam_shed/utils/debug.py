"""
Shared debug logging utility for jam-shed.
"""
import os
import time

_LOG_PATH = os.path.join(os.getcwd(), "jam_shed_debug.log")


def debug_log(msg: str) -> None:
    """Append a timestamped debug message to the log file."""
    with open(_LOG_PATH, "a") as f:
        f.write(f"{time.time()}: {msg}\n")
