import os
from datetime import datetime


def log(level: str, message: str):
    """
    :param level: INFO, ERROR, CRITICAL
    :param message: The log message
    """
    level = level.upper()
    assert level in ['INFO', 'ERROR', 'CRITICAL']

    print(f"> {datetime.now().strftime('%m/%d/%Y %H:%M:%S')} | {level} | {message}\n")