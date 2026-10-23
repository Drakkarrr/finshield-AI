from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="finshield-sdk",
    version="1.0.0",
    author="FinShield AI",
    author_email="support@finshield.ai",
    description="Python SDK for FinShield AI transaction compliance API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/finshield/finshield-sdk-python",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "httpx>=0.27.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "pytest-mock>=3.12.0",
        ],
    },
)
