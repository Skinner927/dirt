from pathlib import Path

from setuptools import find_packages, setup

setup(
    name="tasks",
    version="0.1",
    packages=find_packages(where="src", include=["tasks", "tasks.*"]),
    package_dir={"": "src"},
    install_requires=[
        # In production this would just be "dirt ~= 1.0.0" or something.
        f"dirt@file://{Path(__file__).parent.parent.absolute()}#egg=dirt"
    ],
)
