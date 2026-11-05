"""Configuration helpers for the drift monitoring pipeline.

Callers import ``config`` and ``schema`` explicitly. Keeping package import
lightweight lets notebook bootstrap code load the shared environment before
``src.config.config`` resolves its module-level values.
"""
