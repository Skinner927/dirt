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
        "typing_extensions~=4.9.0",
        "rich~=13.7.0",
        # Nox
        "nox~=2023.4.22",
        # "simple-parsing~=0.1.4",
        "typed-settings[attrs,cattrs]~=23.1.1",
        "attrs",
        "cattrs",
    ],
    extras_require={
        "test": ["pytest~=7.4.0"],
    },
)
