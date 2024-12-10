from setuptools import setup, find_packages

setup(
    name="genews",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'openai>=1.0.0',
        'newsapi-python',
        'fredapi',
        'pandas',
        'numpy',
        'tqdm',
        'ollama',
        'python-dotenv'
    ],
) 
