#!/bin/bash
rm -rf build/html/*
rm en/source/memoryscope*.rst
rm zh_CN/source/memoryscope*.rst
sphinx-apidoc -f -o en/source ../../memoryscope -t template -e
sphinx-apidoc -f -o zh_CN/source ../../memoryscope -t template -e
make clean all