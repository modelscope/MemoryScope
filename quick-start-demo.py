import os

if os.environ.get('DASHSCOPE_API_KEY', None) is None and os.environ.get('API_KEY', None) is None:
    os.environ['DASHSCOPE_API_KEY'] = input('Missing api key from dashscope ( `https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key` ), please input key and press Enter:')

from memoryscope import cli
cli()