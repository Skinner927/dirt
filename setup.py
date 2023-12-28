from setuptools import find_packages, setup

setup(
    name="dirt",
    version="0.1",
    packages=find_packages(where="src", include=["dirt", "dirt.*"]),
    package_dir={"": "src"},
    package_data={"": ["py.typed"]},
    entry_points={
        "console_scripts": ["dirt=dirt.__main__:main"],
    },
    install_requires=[
        "nox==2023.4.22",
    ],
    extras_require={
        "test": ["pytest ~= 7.4.0"],
    },
)
