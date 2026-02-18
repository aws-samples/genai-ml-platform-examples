"""
Setup script for SageMigrator - Intelligent EC2 to SageMaker Migration System
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

# Read requirements
requirements = []
if (this_directory / "requirements.txt").exists():
    requirements = (this_directory / "requirements.txt").read_text().strip().split('\n')

setup(
    name="sagemigrator",
    version="0.1.0",
    author="SageMigrator Team",
    author_email="team@sagemigrator.dev",
    description="Intelligent EC2 to SageMaker Migration System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sagemigrator/sagemigrator",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "hypothesis>=6.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
            "pre-commit>=2.20.0",
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
            "myst-parser>=0.18.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "sagemigrator=sagemigrator.cli:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "sagemigrator": [
            "templates/*.py",
            "templates/*.yaml",
            "templates/*.json",
            "config/*.yaml",
        ],
    },
    zip_safe=False,
)