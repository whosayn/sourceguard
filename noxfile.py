import nox
from pathlib import Path


@nox.session
def lint(session):
    session.install('flake8')
    session.run('flake8')


@nox.session(python="3")
def test(session):
    session.install("invoke")
    test_dir = Path("tests")
    for test_path in test_dir.glob("*test*"):
        session.run("python", "-m", "unittest", test_path.absolute())
