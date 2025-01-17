from setuptools import setup, find_packages

setup(
    name="tiktok_archive",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "yt-dlp>=2023.12.30",
        "requests>=2.31.0",
        "playwright>=1.40.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "test": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.1",
            "pytest-mock>=3.11.1",
        ],
    },
    python_requires=">=3.8",
)
