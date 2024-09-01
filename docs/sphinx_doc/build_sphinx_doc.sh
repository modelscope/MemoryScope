#!/bin/bash
cd docs/sphinx_doc


# remove build
rm -rf build/html/*
rm en/source/memoryscope*.rst
rm zh_CN/source/memoryscope*.rst


# copy related files
cd ../../

cp README.md docs/sphinx_doc/en/source/README.md
cp docs/installation.md docs/sphinx_doc/en/source/docs/installation.md
cp -r docs/images docs/sphinx_doc/en/source/docs/images
cp -r examples docs/sphinx_doc/en/source/examples

cp README_ZH.md docs/sphinx_doc/zh_CN/source/README.md
cp docs/installation_ZH.md docs/sphinx_doc/zh_CN/source/docs/installation.md
cp -r docs/images docs/sphinx_doc/zh_CN/source/docs/images
cp -r examples docs/sphinx_doc/zh_CN/source/examples


# build
cd docs/sphinx_doc
sphinx-apidoc -f -o en/source ../../memoryscope -t template -e
sphinx-apidoc -f -o zh_CN/source ../../memoryscope -t template -e

# clear redundant files
make clean all

rm en/source/README.md
rm en/source/docs/installation.md
rm -rf en/source/docs/images
rm -rf en/source/examples

rm zh_CN/source/README.md
rm zh_CN/source/docs/installation.md
rm -rf zh_CN/source/docs/images
rm -rf zh_CN/source/examples