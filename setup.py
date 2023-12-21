from setuptools import setup, find_packages

setup(
    name="dirt",
    version="0.1",
    packages=find_packages(where="src", include=["dirt", "dirt.*"]),
    package_dir={"": "src"},
    install_requires=[],
    entry_points={
        "console_scripts": ["dirt=dirt.__main__:main"],
    },
)
