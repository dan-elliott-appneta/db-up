"""Setup configuration for db-up."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="db-up",
    version="1.0.0",
    author="DB-Up Contributors",
    description="A simple tool to monitor PostgreSQL database connectivity",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/db-up",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Database",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "psycopg2-binary>=2.9.0",
        "PyYAML>=6.0",
        "python-dotenv>=1.0.0",
        "colorama>=0.4.6",
    ],
    entry_points={
        "console_scripts": [
            "db-up=db_up.main:main",
        ],
    },
)

