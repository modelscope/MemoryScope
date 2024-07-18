#!/bin/bash
rm -rf build/html/*
rm en/source/memory_scope*.rst
rm zh_CN/source/memory_scope*.rst
sphinx-apidoc -f -o en/source ../../memory_scope -t template -e
sphinx-apidoc -f -o zh_CN/source ../../memory_scope -t template -e
make clean all