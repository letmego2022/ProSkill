import os
import json
from config import DATA_FILE,API_KEY,BASE_URL,API_MODEL
from flask import session
from app.models.user import User,History,APIInfo
import uuid
import json
from openai import OpenAI
from app import db
from json_repair import repair_json
import random
import string

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def execute_generated_code(code: str, *args, **kwargs):
    """
    执行 AI 生成的 Python 代码并返回执行结果。
    """
    # 创建一个干净的命名空间，避免访问危险的内置模块
    namespace = {}

    # 编译并执行生成的代码
    try:
        compiled_code = compile(code, "<string>", "exec")
        exec(compiled_code, namespace)
        
        # 假设 AI 生成的代码返回一个结果，或者我们可以从命名空间获取某个执行结果
        result = namespace.get('result', 'No result returned from the generated code.')

        return json.dumps({
            'status': 'success',
            'result': result
        })
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'error': str(e)
        })

def generate_random_filename():
    """生成一个随机的文件名"""
    letters = string.ascii_letters
    random_filename = ''.join(random.choice(letters) for i in range(10))  # 生成一个10字符的随机文件名
    return random_filename + '.feature'

def save_gherkin_code(gherkin_code, directory, apiinfo):
    """将Gherkin代码保存到指定目录，并返回文件路径"""
    if not os.path.exists(directory):
        os.makedirs(directory)  # 如果目录不存在，则创建目录

    random_filename = generate_random_filename()
    file_path = os.path.join(directory, random_filename)

    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(gherkin_code)

    # 将apiinfo和file_path存入数据库
    api_info_record = APIInfo(api_info=apiinfo, file_path=random_filename)
    db.session.add(api_info_record)
    db.session.commit()

    return file_path

# 读取存储的数据
def read_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    return {}

# 写入存储的数据
def write_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def create_history_entry(user_id):
    __bind_key__ = 'user'  # 使用 user 数据库
    session_id = str(uuid.uuid4())
    initial_history = [{"role": "system", "content": read_data().get("prompt1", "")}]
    history_entry = History(user_id=user_id, session_id=session_id, messages=json.dumps(initial_history))
    db.session.add(history_entry)
    db.session.commit()
    return history_entry

def create_history_entry_m(user_id):
    __bind_key__ = 'user'  # 使用 user 数据库
    session_id = str(uuid.uuid4())
    initial_history = [{"role": "system", "content": read_data().get("prompt5", "")}]
    history_entry = History(user_id=user_id, session_id=session_id, messages=json.dumps(initial_history))
    db.session.add(history_entry)
    db.session.commit()
    return history_entry

def chat_mode(query, stream=False):
    __bind_key__ = 'user'  # 使用 user 数据库
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401

    history_entry = History.query.filter_by(user_id=user_id).order_by(History.id.desc()).first()
    if not history_entry:
        history_entry = create_history_entry(user_id)

    history = json.loads(history_entry.messages)
    history.append({"role": "user", "content": query, "type": "json_object", "partial": True})

    if len(history) > 6:
        inithistory = history[:2] + history[4:]
    else:
        inithistory = history

    if stream:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3, stream=True)
        collected_messages = []
        for chunk in completion:
            chunk_message = chunk.choices[0].delta.content
            if not chunk_message:
                continue
            collected_messages.append(chunk_message)
            yield chunk_message
        result = ''.join(collected_messages)
    else:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3)
        result = completion.choices[0].message.content

    history.append({"role": "assistant", "content": result})
    history_entry.messages = json.dumps(history)
    db.session.commit()
    return result

def chat_mode_demo(messages, stream=False):
    if stream:
        # 创建流式输出生成器
        completion = client.chat.completions.create(
            model=API_MODEL, messages=messages, temperature=0.3, stream=True
        )
        collected_messages = []

        def stream_result():
            nonlocal collected_messages
            for chunk in completion:
                chunk_message = chunk.choices[0].delta.content
                if chunk_message:
                    collected_messages.append(chunk_message)
                    yield chunk_message

        # 通过生成器 yield 每个数据块，同时收集数据
        stream_output = stream_result()

        # 返回生成器和最终结果
        return stream_output, collected_messages
    else:
        # 非流式模式，直接返回结果
        completion = client.chat.completions.create(
            model=API_MODEL, messages=messages, temperature=0.3
        )
        result = completion.choices[0].message.content
        return result

def chat_mode_py(query, stream=False):
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401
    if stream:
        # 创建流式输出生成器
        completion = client.chat.completions.create(
            model=API_MODEL, messages=query, temperature=0.3, stream=True
        )
        collected_messages = []

        def stream_result():
            nonlocal collected_messages
            for chunk in completion:
                chunk_message = chunk.choices[0].delta.content
                if chunk_message:
                    collected_messages.append(chunk_message)
                    yield f"data: {chunk_message}\n\n"

        # 通过生成器 yield 每个数据块，同时收集数据
        stream_output = stream_result()

        # 返回生成器和最终结果
        return stream_output, collected_messages
    else:
        # 非流式模式，直接返回结果
        completion = client.chat.completions.create(
            model=API_MODEL, messages=query, temperature=0.3
        )
        result = completion.choices[0].message.content
        return result

def checkjson(one_with_json):
    try:
        if '```' in one_with_json:
            json_string = one_with_json.split('```')[1].strip()[4:].strip()
        else:
            json_string = one_with_json
        repaired_json_string = repair_json(json_string)
        if repaired_json_string:
            context = json.loads(repaired_json_string)
        else:
            context = []
    except json.JSONDecodeError:
        context = []
    return context

def checkGherkin(one_with_json):
    try:
        if '```' in one_with_json:
            json_string = one_with_json.split('```')[1].strip()[7:].strip()
        else:
            json_string = one_with_json
    except:
        json_string = ""
    return json_string

def checkPython(one_with_json):
    try:
        if '```' in one_with_json:
            json_string = one_with_json.split('```')[1].strip()[6:].strip()
        else:
            json_string = one_with_json
    except:
        json_string = ""
    return json_string

def chat_mode_script(query, stream=False):
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401
    if stream:
        # 创建流式输出生成器
        completion = client.chat.completions.create(
            model=API_MODEL, messages=query, temperature=0.3, stream=True
        )
        collected_messages = []

        def stream_result():
            nonlocal collected_messages
            for chunk in completion:
                chunk_message = chunk.choices[0].delta.content
                if chunk_message:
                    collected_messages.append(chunk_message)
                    yield chunk_message

        # 通过生成器 yield 每个数据块，同时收集数据
        stream_output = stream_result()

        # 返回生成器和最终结果
        return stream_output, collected_messages
    else:
        # 非流式模式，直接返回结果
        completion = client.chat.completions.create(
            model=API_MODEL, messages=query, temperature=0.3
        )
        result = completion.choices[0].message.content
        return result

def chat_mode_one(query, stream=False):
    __bind_key__ = 'user'  # 使用 user 数据库
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401

    history_entry = History.query.filter_by(user_id=user_id).order_by(History.id.desc()).first()
    if not history_entry:
        history_entry = create_history_entry(user_id)

    history = json.loads(history_entry.messages)
    history.append({"role": "user", "content": query, "type": "json_object", "partial": True})

    if len(history) > 6:
        inithistory = history[:2] + history[4:]
    else:
        inithistory = history

    if stream:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3, stream=True)
        collected_messages = []
        for chunk in completion:
            chunk_message = chunk.choices[0].delta.content
            if not chunk_message:
                continue
            collected_messages.append(chunk_message)
            yield chunk_message
        result = ''.join(collected_messages)
    else:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3)
        result = completion.choices[0].message.content

    history.append({"role": "assistant", "content": result})
    history_entry.messages = json.dumps(history)
    db.session.commit()
    return result

def chat_mode_manua(query, stream=False):
    __bind_key__ = 'user'  # 使用 user 数据库
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401

    history_entry = History.query.filter_by(user_id=user_id).order_by(History.id.desc()).first()
    if not history_entry:
        history_entry = create_history_entry_m(user_id)

    history = json.loads(history_entry.messages)
    history.append({"role": "user", "content": query, "type": "json_object", "partial": True})

    if len(history) > 6:
        inithistory = history[:2] + history[4:]
    else:
        inithistory = history

    if stream:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3, stream=True)
        collected_messages = []
        for chunk in completion:
            chunk_message = chunk.choices[0].delta.content
            if not chunk_message:
                continue
            collected_messages.append(chunk_message)
            yield chunk_message
        result = ''.join(collected_messages)
    else:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3)
        result = completion.choices[0].message.content

    history.append({"role": "assistant", "content": result})
    history_entry.messages = json.dumps(history)
    db.session.commit()
    return result


def chat_mode_boot(query, stream=False):
    __bind_key__ = 'user'  # 使用 user 数据库
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401

    history_entry = History.query.filter_by(user_id=user_id).order_by(History.id.desc()).first()
    if not history_entry:
        history_entry = create_history_entry_m(user_id)

    history = json.loads(history_entry.messages)
    history.append({"role": "user", "content": query})
    if len(history) > 6:
        inithistory = history[:2] + history[4:]
    else:
        inithistory = history

    if stream:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3, stream=True)
        collected_messages = []
        for chunk in completion:
            chunk_message = chunk.choices[0].delta.content
            if not chunk_message:
                continue
            collected_messages.append(chunk_message)
            yield chunk_message
        result = ''.join(collected_messages)
    else:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3)
        result = completion.choices[0].message.content

    history.append({"role": "assistant", "content": result})
    history_entry.messages = json.dumps(history)
    db.session.commit()
    return result

def chat_mode_Drive(query, stream=False):
    __bind_key__ = 'user'  # 使用 user 数据库
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401

    history_entry = History.query.filter_by(user_id=user_id).order_by(History.id.desc()).first()
    if not history_entry:
        history_entry = create_history_entry_m(user_id)

    history = json.loads(history_entry.messages)
    history.append({"role": "user", "content": query})
    if len(history) > 8:
        inithistory = history[:2] + history[4:]
    else:
        inithistory = history

    if stream:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3, stream=True)
        collected_messages = []
        for chunk in completion:
            chunk_message = chunk.choices[0].delta.content
            if not chunk_message:
                continue
            collected_messages.append(chunk_message)
            yield chunk_message
        result = ''.join(collected_messages)
        if 'python' in result:
            pythoncode = checkPython(result)
            yield f'\n -- 运作中 --'
            # 执行生成的代码
            response = json.loads(execute_generated_code(pythoncode))
            # res = response["result"]
            result = result + f"代码运行结果为：{response}"
            yield f'\n 结果：{response}'
            # yield f'\n 结果：{res}'
    else:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3)
        result = completion.choices[0].message.content

    history.append({"role": "assistant", "content": result})
    history_entry.messages = json.dumps(history)
    db.session.commit()
    return result


def chat_mode_staff(query, stream=False):
    __bind_key__ = 'user'  # 使用 user 数据库
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401

    history_entry = History.query.filter_by(user_id=user_id).order_by(History.id.desc()).first()
    if not history_entry:
        history_entry = create_history_entry_m(user_id)

    history = json.loads(history_entry.messages)
    query1 = query
    history.append({"role": "user", "content": query1})
    if len(history) > 8:
        inithistory = history[:2] + history[4:]
    else:
        inithistory = history

    if stream:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3, stream=True)
        collected_messages = []
        for chunk in completion:
            chunk_message = chunk.choices[0].delta.content
            if not chunk_message:
                continue
            collected_messages.append(chunk_message)
            yield chunk_message
        result = ''.join(collected_messages)
    else:
        completion = client.chat.completions.create(model=API_MODEL, messages=inithistory, temperature=0.3)
        result = completion.choices[0].message.content

    history.append({"role": "assistant", "content": result})
    history_entry.messages = json.dumps(history)
    db.session.commit()
    return result