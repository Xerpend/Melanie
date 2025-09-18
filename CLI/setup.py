"""
Setup script for Melanie CLI.

Provides installation configuration for development and distribution.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    with open(requirements_path) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="melanie-cli",
    version="1.0.0",
    description="Melanie AI Terminal Coder - Intelligent coding assistant with agent coordination",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Melanie AI Team",
    author_email="team@melanie.ai",
    url="https://github.com/melanie-ai/melanie-cli",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "melanie-cli=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Software Development :: Testing",
        "Topic :: Utilities",
    ],
    keywords="ai coding assistant cli terminal automation",
    project_urls={
        "Bug Reports": "https://github.com/melanie-ai/melanie-cli/issues",
        "Source": "https://github.com/melanie-ai/melanie-cli",
        "Documentation": "https://docs.melanie.ai/cli",
    },
)