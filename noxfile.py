import nox


@nox.session
def lint(session):
    session.install("flake8")
    session.run("flake8")


@nox.session
def test(session):
    session.install(".")
    session.run("python", "-m", "unittest", "discover", "-s", "tests", "-v")
