import os

if os.environ.get('DASHSCOPE_API_KEY', None) is None:
    os.environ['DASHSCOPE_API_KEY'] = input('Missing api key from dashscope ( https:// ???? ), please input key and press Enter:')

from memoryscope import cli
cli()