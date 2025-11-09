from setuptools import setup, find_packages

setup(
    name="albatross_protocol",
    version="0.1.0",
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        "Flask==3.0.3",
        "numpy==1.26.4",
        "requests==2.32.3",
        "sympy==1.12.1",
        "matplotlib==3.9.0",
        "networkx==3.1",
    ],
    entry_points={
        'console_scripts': [
            'albatross=src.main:main',
        ],
    },
    author="OCTAVIAN PETREA",
    author_email="octav.petrea@gmail.com",
    description="Simulación del protocolo ALBATROSS en una red distribuida simulada con Flask",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/octaviope/Albatross",
    python_requires='>=3.8',
)
