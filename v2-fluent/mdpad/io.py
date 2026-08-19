"""文件读写与 HTML 导出。"""
import markdown

# 读取时尝试的编码顺序
READ_ENCODINGS = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'latin-1']

EXPORT_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MDPad 导出</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            background-color: #ffffff;
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }}
        h1 {{ font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
        h3 {{ font-size: 1.25em; }}
        code {{
            background-color: rgba(27,31,35,0.05);
            border-radius: 3px;
            padding: 0.2em 0.4em;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
        }}
        pre {{
            background-color: #f6f8fa;
            border-radius: 3px;
            padding: 16px;
            overflow: auto;
        }}
        blockquote {{
            border-left: 4px solid #dfe2e5;
            padding-left: 16px;
            color: #6a737d;
            margin-left: 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
        }}
        th, td {{
            border: 1px solid #dfe2e5;
            padding: 6px 13px;
        }}
        th {{
            background-color: #f6f8fa;
        }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        img {{ max-width: 100%; }}
        br {{
            display: block;
            content: "";
            margin-top: 0.5em;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""


def read_text_file(file_path):
    """读取文本文件，自动尝试多种编码；全部失败时以 UTF-8 忽略错误兜底。"""
    content = None
    for encoding in READ_ENCODINGS:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        with open(file_path, 'rb') as file:
            content = file.read().decode('utf-8', errors='ignore')
    return content


def write_text_file(file_path, text):
    """以 UTF-8 写入文本文件。"""
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(text)


def render_export_html(markdown_text):
    """把 Markdown 渲染成完整 HTML 文档。"""
    html_content = markdown.markdown(
        markdown_text,
        extensions=['extra', 'codehilite', 'toc'],
    )
    return EXPORT_HTML_TEMPLATE.format(html_content=html_content)
