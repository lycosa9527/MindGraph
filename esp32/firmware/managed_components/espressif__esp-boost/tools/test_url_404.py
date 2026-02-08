# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import sys
import re
import requests


def extract_urls_from_markdown(file_path):
    """从 Markdown 文件中提取所有 URL"""
    url_pattern = re.compile(r'\[.*?\]\((https?://[^\s)]+)\)')
    urls = []

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                urls.extend(url_pattern.findall(line))
    except Exception as e:
        print(f'❌ 无法读取文件 {file_path}: {e}')

    return urls


def check_url(url):
    """检查 URL 是否返回 404"""
    try:
        response = requests.get(url, timeout=5)
        if '404 - page not found' in response.text or response.status_code == 404:
            return False
        return True
    except requests.RequestException:
        return False


def main():
    if len(sys.argv) < 2:
        print('用法: python check_markdown_urls.py <markdown文件路径1> <markdown文件路径2> ...')
        sys.exit(1)

    file_paths = sys.argv[1:]

    all_urls = {}
    for file_path in file_paths:
        urls = extract_urls_from_markdown(file_path)
        if urls:
            all_urls[file_path] = urls

    if not all_urls:
        print('未找到任何 URL')
        sys.exit(0)

    print(f'检测 {sum(len(urls) for urls in all_urls.values())} 个 URL...\n')

    for file_path, urls in all_urls.items():
        print(f'� 文件: {file_path}')
        for url in urls:
            status = '✅ 正常' if check_url(url) else '❌ 404'
            print(f'  {status} - {url}')
        print()


if __name__ == '__main__':
    main()
