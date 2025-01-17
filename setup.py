from setuptools import setup, find_packages

setup(
    name="tiktok-archiver",
    version="1.0.0",
    packages=find_packages(),
    package_dir={"": "src"},
    install_requires=[
        "yt-dlp>=2023.12.30",
        "requests>=2.31.0",
        "playwright>=1.40.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "tiktok-archiver=main:main",
        ],
    },
)
