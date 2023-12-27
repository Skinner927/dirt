from setuptools import setup, find_packages

setup(
    name="dirt",
    version="0.1",
    packages=find_packages(where="src", include=["dirt", "dirt.*"]),
    package_dir={"": "src"},
    package_data={"": ["py.typed"]},
    install_requires=[
        "nox==2023.4.22",
    ],
    entry_points={
        "console_scripts": ["dirt=dirt.__main__:main"],
    },
)
