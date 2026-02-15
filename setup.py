"""Setup configuration for PII Toolkit package installation."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = (
    readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""
)

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file, "r", encoding="utf-8") as f:
        requirements = [
            line.strip() for line in f if line.strip() and not line.startswith("#")
        ]

extras_require = {
    # Development / testing
    "dev": [
        "pytest~=8.0.0",
        "pytest-cov~=4.1.0",
        "pytest-mock~=3.14.0",
    ],
    # File format processors
    "office": [
        "python-docx~=1.2.0",
        "striprtf~=0.0.26",
        "odfpy~=1.4.1",
        "openpyxl~=3.1.0",
        "xlrd~=2.0.1",
        "extract-msg~=0.55.0",
        "python-pptx~=0.6.23",
        "PyYAML~=6.0.1",
    ],
    "images": ["Pillow>=10.0.0"],
    # Engines
    "gliner": ["gliner~=0.2.22"],
    "spacy": ["spacy>=3.7.0"],
    "llm": ["pydantic-ai>=0.0.10", "pydantic>=2.0.0", "requests>=2.31.0"],
    # File type detection
    "magic": ["python-magic>=0.4.27", "filetype>=1.2.0"],
}
extras_require["all"] = sorted({dep for group in extras_require.values() for dep in group})

setup(
    name="pii-toolkit",
    version="1.0.0",
    description="Scan directories for personally identifiable information",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="PII Toolkit Contributors",
    url="https://github.com/lichtbaer/pbd-toolkit",
    packages=find_packages(exclude=["tests", "tests.*"]),
    # Codebase uses Python 3.10+ syntax (e.g. `str | None`, `list[str]`).
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require=extras_require,
    include_package_data=True,
    package_data={
        "core": ["config_types.json"],
    },
    entry_points={
        "console_scripts": [
            "pii-toolkit=main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
