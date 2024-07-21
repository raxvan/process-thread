from setuptools import setup, find_packages

setup(
    name = "process-thread",
    version = "0.0.1",
    description = "Utinity that helps with running processes.",
    long_description = open('README.md').read(),
    long_description_content_type = 'text/markdown',
    packages = find_packages(),
    install_requires = [
        "psutil"
    ],
    python_requires = '>=3.8',
)