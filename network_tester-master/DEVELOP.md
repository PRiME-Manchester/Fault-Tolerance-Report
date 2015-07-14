Development
-----------

### `virtualenv` setup

We recommend working in a [virtualenv](https://pypi.python.org/pypi/virtualenv)
which can be set up like so:

    virtualenv network_tester_virtualenv
    cd network_tester_virtualenv
    . bin/activate

### Installing `network_tester`

A development installation of `network_tester` can be installed
using [setuptools](https://pypi.python.org/pypi/setuptools) as usual:

    git clone git@github.com:project-rig/network_tester.git
    cd network_tester
    python setup.py develop

### Running Tests

We use [py.test](http://pytest.org) to test Network Tester,
[pytest-cov](https://pypi.python.org/pypi/pytest-cov/1.8.1) to generate
coverage reports and the [flake8](https://pypi.python.org/pypi/flake8) coding
standard checker. Developers should be careful to test for compliance before
pushing code.

The required tools can be installed via pip using:

    pip install -r requirements-test.txt

The tests can now be run using:

    py.test tests

Or to run tests on all supported Python versions:

    pip install tox
    tox

Some tests require real SpiNNaker hardware to run. To enable these, supply the
hostname of a booted SpiNNaker board with at least two working chips.

    py.test tests --spinnaker HOSTNAME


To get a test coverage report:

    py.test testst --cov tests --cov network_tester --cov-report html

