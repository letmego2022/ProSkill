

class FileHandler:
    def __init__(self, filename):
        self.filename = filename

    def read_file(self):
        """从文件中读取内容"""
        try:
            with open(self.filename, 'r', encoding='utf-8') as file:
                content = file.read()
            return content
        except FileNotFoundError:
            return "文件未找到。"
        except Exception as e:
            return f"读取文件时发生错误：{e}"
    def process_text(self, content):
        """处理文本并提取Python代码"""
        python_code = False
        try:
            if '```python' in content:
                tmplist = content.split('```')
                for item in tmplist:
                    if item.startswith('python'):
                        python_code = item[6:]
                        break
            return python_code
        except Exception as e:
            return f"处理文本时发生错误：{e}"
    def write_file(self, content):
        """将更新后的内容存入文件"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as file:
                file.write(content)
            return "内容已更新。"
        except Exception as e:
            return f"写入文件时发生错误：{e}"
			
def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        return "文件未找到，请检查路径是否正确。"
    except Exception as e:
        return f"读取文件时发生错误：{e}"