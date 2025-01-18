from setuptools import setup, find_packages

setup(
    name="resume-generator",
    version="0.1",
    packages=find_packages(include=['backend', 'backend.*']),
    install_requires=[
        "fastapi",
        "uvicorn",
        "requests",
        "pydantic",
        "langchain",
        "langgraph",
        "openai",
        "python-multipart",
        "sqlalchemy",
        "aiofiles",
        "jinja2"
    ],
)