from app import db
import sqlite3
import subprocess
import os
import random
import string
from config import DATABASE_PATH, TESTS_JAVASTEP_DIR, TESTS_Feature_DIR

class JavaCodeProcessor:
    def __init__(self, db_path, apipath, text, userid):
        self.db_path = db_path
        self.apipath = apipath
        self.text = text
        self.connection = None
        self.userid = userid
        self.funcname = '_'.join(self.apipath.rsplit('/', 2)[-2:])

        # 检查数据库文件是否存在
        if not os.path.exists(self.db_path):
            # 文件不存在，创建数据库连接和表
            self.connection = self.create_db_connection()
        else:
            # 文件存在，打开现有数据库连接
            self.connection = self.ensure_db_connection()

    def create_db_connection(self):
        # 创建数据库连接，并初始化表
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY,
                file_name TEXT,
                api_path TEXT,
				test_res TEXT,
                test_outcome TEXT,
                runs INTEGER,
                output TEXT,
                python_code TEXT,
				userid TEXT
            )
        ''')
        connection.commit()
        return connection

    def ensure_db_connection(self):
        # 确保数据库连接存在，但不创建新表
        return sqlite3.connect(self.db_path)
    def write2py(self, pystring, length=10):
        random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        file_name = f'{TESTS_JAVASTEP_DIR}{self.funcname}_{random_name}api_test.java'
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        with open(file_name, 'w', encoding='utf-8') as file:
            file.write(pystring)
        return file_name
    
    def write2Feature(self, pystring, length=10):
        random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        file_name = f'{TESTS_Feature_DIR}{self.funcname}_{random_name}.feature'
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        with open(file_name, 'w', encoding='utf-8') as file:
            file.write(pystring)
        return file_name

    def pytestcommand(self, file_name):
        command = f"pytest {file_name}"
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            outcome = 'Failed'
        else:
            outcome = 'Passed'
        output = result.stdout
        # 尝试删除文件，如果文件不存在则忽略错误
        #try:
        #    os.remove(file_name)
        #except FileNotFoundError:
        #    pass  # 如果文件不存在，我们可以选择忽略错误
        return outcome, output

    def process_text(self):
        if '```' in self.text:
            tmplist = self.text.split('```')
            for item in tmplist:
                if item.startswith('java'):
                    python_string = item[4:]
                    file_name = self.write2py(python_string)
                    self.save_result(file_name, "未运行", "未运行", python_string)
                elif item.startswith('gherkin'):
                    python_string = item[7:]
                    file_name = self.write2Feature(python_string)
                    # self.save_result(file_name, "未运行", "未运行", python_string)

    def save_result(self, file_name, outcome, output, python_string):
        if "FAILURES" not in output:
            test_res = 'P'
        else:
            test_res = 'F'
        # 搜索匹配项
        if "100%" in output:
            runs = '100'
        else:
            runs = '0'
        cursor = self.connection.cursor()
        cursor.execute('''
            INSERT INTO test_results (file_name, api_path,test_res, test_outcome, runs, output, python_code, userid)
            VALUES (?, ?, ?, ?, ?, ?,?,?)
        ''', (file_name, self.funcname, test_res,outcome, int(runs), output, python_string, self.userid))
        self.connection.commit()

class CodeProcessor:
    def __init__(self, db_path, apipath, text, userid):
        self.db_path = db_path
        self.apipath = apipath
        self.text = text
        self.connection = None
        self.userid = userid
        self.funcname = '_'.join(self.apipath.rsplit('/', 2)[-2:])

        # 检查数据库文件是否存在
        if not os.path.exists(self.db_path):
            # 文件不存在，创建数据库连接和表
            self.connection = self.create_db_connection()
        else:
            # 文件存在，打开现有数据库连接
            self.connection = self.ensure_db_connection()

    def create_db_connection(self):
        # 创建数据库连接，并初始化表
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY,
                file_name TEXT,
                api_path TEXT,
				test_res TEXT,
                test_outcome TEXT,
                runs INTEGER,
                output TEXT,
                python_code TEXT,
				userid TEXT
            )
        ''')
        connection.commit()
        return connection

    def ensure_db_connection(self):
        # 确保数据库连接存在，但不创建新表
        return sqlite3.connect(self.db_path)
    def write2py(self, pystring, length=10):
        random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        file_name = f'../pytest/TestCase/{self.funcname}_{random_name}api_test.py'
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        with open(file_name, 'w', encoding='utf-8') as file:
            file.write(pystring)
        return file_name

    def pytestcommand(self, file_name):
        command = f"pytest {file_name}"
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            outcome = 'Failed'
        else:
            outcome = 'Passed'
        output = result.stdout
        # 尝试删除文件，如果文件不存在则忽略错误
        #try:
        #    os.remove(file_name)
        #except FileNotFoundError:
        #    pass  # 如果文件不存在，我们可以选择忽略错误
        return outcome, output

    def process_text(self):
        if '```' in self.text:
            tmplist = self.text.split('```')
            for item in tmplist:
                if item.startswith('python'):
                    python_string = item[6:]
                    file_name = self.write2py(python_string)
                    outcome, output = self.pytestcommand(file_name)
                    self.save_result(file_name, outcome, output, python_string)

    def save_result(self, file_name, outcome, output, python_string):
        if "FAILURES" not in output:
            test_res = 'P'
        else:
            test_res = 'F'
        # 搜索匹配项
        if "100%" in output:
            runs = '100'
        else:
            runs = '0'
        cursor = self.connection.cursor()
        cursor.execute('''
            INSERT INTO test_results (file_name, api_path,test_res, test_outcome, runs, output, python_code, userid)
            VALUES (?, ?, ?, ?, ?, ?,?,?)
        ''', (file_name, self.funcname, test_res,outcome, int(runs), output, python_string, self.userid))
        self.connection.commit()

class ReCodeProcessor:
    def __init__(self, python_string, script_id):
        self.python_string = python_string
        self.script_id = script_id

    def write2py(self, pystring, length=10):
        random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        connection = sqlite3.connect(DATABASE_PATH)
        cursor = connection.cursor()
        # 根据id从数据库中获取python_code
        cursor.execute('SELECT file_name FROM test_results WHERE id=?', (self.script_id,))
        result = cursor.fetchone()
        file_name = result[0]
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        with open(file_name, 'w', encoding='utf-8') as file:
            file.write(pystring)
        return file_name

    def pytestcommand(self, file_name):
        command = f"pytest {file_name}"
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            outcome = 'Failed'
        else:
            outcome = 'Passed'
        output = result.stdout
        # 尝试删除文件，如果文件不存在则忽略错误
        #try:
        #    os.remove(file_name)
        #except FileNotFoundError:
        #    pass  # 如果文件不存在，我们可以选择忽略错误
        return outcome, output

    def process_text(self):
        file_name = self.write2py(self.python_string)
        outcome, output = self.pytestcommand(file_name)
        if "FAILURES" not in output:
            test_res = 'P'
        else:
            test_res = 'F'
        if "100%" in output:
            runs = '100'
        else:
            runs = '0'
        return test_res,runs,output,outcome,self.script_id