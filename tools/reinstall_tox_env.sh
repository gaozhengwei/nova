#!/bin/bash

TOP=$(git rev-parse --show-toplevel)
cd ${TOP}

rm -rf .tox
tar xjf tox.tar.bz2

tox_version=$(tox --version| awk '{print $1}')

for venv in pep8 py26
do
    sed -i "s|/root/zw/nova/.venv/bin/python|/usr/bin/python|" .tox/${venv}/.tox-config1
    sed -i "s/1.8.1 0 0 1/${tox_version} 0 0 1/" .tox/${venv}/.tox-config1
    sed -i "s/1.8.1 0 1 1/${tox_version} 0 0 1/" .tox/${venv}/.tox-config1
    sed -i "s|/root/zw/nova|${TOP}|" .tox/${venv}/.tox-config1
    sed -i "s|/root/zw/nova||" .tox/${venv}/lib/python2.6/site-packages/easy-install.pth
    find .tox/${venv}/bin -type f -exec sed -i "s|/root/zw/nova|${TOP}|" {} \;

    source .tox/${venv}/bin/activate
    python setup.py develop --no-deps
done
