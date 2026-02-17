from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = [
        line.strip() for line in f if line.strip() and not line.startswith("#")
    ]

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="unesco-risk-modeling",
    version="0.1.0",
    description="Risk Modeling of UNESCO Heritage Sites in Europe",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ali Erguney",
    url="https://github.com/alierguney1/Risk-Modeling-of-UNESCO-Heritage-Sites",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: GIS",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
    ],
)
