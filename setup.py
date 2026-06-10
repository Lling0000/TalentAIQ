"""Compatibility setup file for older pip/setuptools environments."""

from setuptools import find_packages, setup


setup(
    name="talentaiq-lite",
    version="0.1.0",
    description="Local-first, candidate-authorized AI-native engineering evidence generator.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(include=["talentaiq", "talentaiq.*"]),
    python_requires=">=3.9",
    entry_points={"console_scripts": ["talentaiq=talentaiq.cli:main"]},
)
