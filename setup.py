"""Setup script for pi-planner-console."""
from setuptools import setup, find_packages

setup(
    name="pi-planner-console",
    version="0.1.0",
    description="AI-driven PI Planning console application with multi-agent workflow",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "rich>=13.0.0",
        "openai>=1.0.0",
        "azure-identity>=1.15.0",
        "azure-devops>=7.0.0",
        "pyautogen>=0.2.0",
        "aiofiles>=23.0.0",
        "python-dateutil>=2.8.0",
    ],
    entry_points={
        "console_scripts": [
            "pi-planner=src.main:main",
        ],
    },
)

