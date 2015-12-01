#!/bin/bash

TOP=$(git rev-parse --show-toplevel)
cd ${TOP}

rm -rf .tox
tar xjf tox.tar.bz2

tox_version=$(tox --version| awk '{print $1}')

for venv in pep8 py26
do
    sed -i "s/1.6.0 0 0 1/${tox_version} 0 0 1/" .tox/${venv}/.tox-config1
    sed -i "s|/root/nova|${TOP}|" .tox/${venv}/.tox-config1
    sed -i "s|/root/nova||" .tox/${venv}/lib/python2.6/site-packages/easy-install.pth
    find .tox/${venv}/bin -type f -exec sed -i "s|/root/nova|${TOP}|" {} \;

    source .tox/${venv}/bin/activate
    python setup.py develop --no-deps
done
