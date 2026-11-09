"""Emplacements des fichiers de l'application, depuis les sources ou une fois installée (.exe)."""
import os
import sys


def frozen():
    return bool(getattr(sys, "frozen", False))


def app_dir():
    """Dossier contenant island.py (sources) ou DynamicIsland.exe (application installée)."""
    if frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource(*parts):
    return os.path.join(app_dir(), *parts)
