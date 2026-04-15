from setuptools import setup, find_packages
setup(
    name="aot-harness",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["anthropic>=0.40.0"],
    extras_require={"mcp": ["mcp>=1.0.0"]},
    python_requires=">=3.11",
    author="Ronny Schumann",
    description="Agent Harness with Atom of Thoughts (AoT) reasoning",
    url="https://github.com/ronnyschumann1983-boop/aot-harness",
    license="MIT",
)
