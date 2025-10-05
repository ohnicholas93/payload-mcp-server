"""
Payload CMS MCP Server Package

A Model Context Protocol (MCP) server for interacting with Payload CMS.
"""

import sys
import logging

# Defer the import to avoid circular dependency when running as module
def __getattr__(name):
    if name == "main":
        from .server import main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["main"]