#!/bin/bash
cd "$(dirname "$0")"

function clean {
  rm -r dist || echo "skip"
  rm -r build || echo "skip"
  rm -r vygdb.egg-info || echo "skip"
  rm -r .eggs || echo "skip"
  rm -r src/vygdb.egg-info || echo "skip"
  rm -r vygdb/__pycache__ || echo "skip"
  rm -r .pytest_cache || echo "skip"
  rm -r tests/__pycache__ || echo "skip"
}

# pip3 install -e .

clean
python3 setup.py sdist bdist_wheel
python3 setup.py test
python3 -m twine upload dist/*
# use the username __token__ and the password (in the notes of pypi in vault)
