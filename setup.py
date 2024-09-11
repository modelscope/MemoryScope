"""
# 1. remove old temp folders
rm -rf dist build

# 2. then, build
python setup.py sdist bdist_wheel

# 3. finally, upload
twine upload dist/*

rm -rf dist build && python setup.py sdist bdist_wheel && twine upload dist/*
"""

import os

import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


def _process_requirements():
    packages = open('requirements.txt').read().strip().split('\n')
    requires = []
    for pkg in packages:
        if pkg.startswith('git+ssh'):
            return_code = os.system('pip install {}'.format(pkg))
            assert return_code == 0, 'error, status_code is: {}, exit!'.format(return_code)
        else:
            requires.append(pkg)
    return requires


def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            if filename.endswith('yaml'):
                paths.append(os.path.join('..', path, filename))
    return paths


extra_files = package_files('memoryscope')

authors = [
    {"name": "Li Yu", "email": "jinli.yl@alibaba-inc.com"},
    {"name": "Tiancheng Qin", "email": "qiancheng.qtc@alibaba-inc.com"},
    {"name": "Qingxu Fu", "email": "fuqingxu.fqx@alibaba-inc.com"},
    {"name": "Sen Huang", "email": "huangsen.huang@alibaba-inc.com"},
    {"name": "Xianzhe Xu", "email": "xianzhe.xxz@alibaba-inc.com"},
    {"name": "Zhaoyang Liu", "email": "jingmu.lzy@alibaba-inc.com"},
    {"name": "Boyin Liu", "email": "liuboyin.lby@alibaba-inc.com"},
]

setuptools.setup(
    name="memoryscope",
    version="0.1.1.0",
    author=', '.join([author['name'] for author in authors]),
    author_email=', '.join([author['email'] for author in authors]),
    description="MemoryScope is a powerful and flexible long term memory system for LLM chatbots. It consists of a "
                "memory database and three customizable system operations, which can be flexibly combined to provide "
                "robust long term memory services for your LLM chatbot.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/modelscope/memoryscope",
    project_urls={
        "Bug Tracker": "https://github.com/modelscope/memoryscope/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "."},
    package_data={"": extra_files},
    include_package_data=True,
    entry_points={
        'console_scripts': ['memoryscope=memoryscope:cli'],
    },
    packages=setuptools.find_packages(where="."),
    python_requires=">=3.10",
    install_requires=_process_requirements(),
)
