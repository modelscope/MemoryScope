#!/bin/bash

# remove build
rm -rf build/html/*
rm -rf en/source/memoryscope*.rst
rm -rf zh/source/memoryscope*.rst


# copy related files
cd ../../

cp README.md docs/sphinx_doc/en/source/README.md
cp docs/installation.md docs/sphinx_doc/en/source/docs/installation.md
cp docs/contribution.md docs/sphinx_doc/en/source/docs/contribution.md
cp -r docs/images docs/sphinx_doc/en/source/docs/images
cp -r examples docs/sphinx_doc/en/source/examples

cp README_ZH.md docs/sphinx_doc/zh/source/README.md
cp docs/installation_zh.md docs/sphinx_doc/zh/source/docs/installation.md
cp docs/contribution_zh.md docs/sphinx_doc/zh/source/docs/contribution.md
cp -r docs/images docs/sphinx_doc/zh/source/docs/images
cp -r examples docs/sphinx_doc/zh/source/examples

# build
cd docs/sphinx_doc
sphinx-apidoc -f -o en/source ../../memoryscope -t template -e
sphinx-apidoc -f -o zh/source ../../memoryscope -t template -e

# clear redundant files
make clean all

rm en/source/README.md
rm en/source/docs/installation.md
rm en/source/docs/contribution.md
rm -rf en/source/docs/images
rm -rf en/source/examples

rm zh/source/README.md
rm zh/source/docs/installation.md
rm zh/source/docs/contribution.md
rm -rf zh/source/docs/images
rm -rf zh/source/examples