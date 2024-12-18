from flask import jsonify,Blueprint, session,url_for, request, render_template, redirect, flash,send_from_directory
from config import STAFF_FILE_PATH,CV_FILE,CV_EN_FILE
import os
import json
from app.models.user import User
from app.utils.api_utils import extract_text_from_file
from app.utils.utils import chat_mode_script
import psutil
import time

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}  # 允许的文件类型

def load_resumes(jsonfile):
    """加载简历 JSON 数据"""
    if os.path.exists(jsonfile):
        with open(jsonfile, 'r', encoding='utf-8') as file:
            return json.load(file)
    return {}

def save_resumes(jsonfile,data):
    """保存简历 JSON 数据"""
    with open(jsonfile, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
# 确保文件夹存在
if not os.path.exists(STAFF_FILE_PATH):
    os.makedirs(STAFF_FILE_PATH)
# 创建 Blueprint 实例
fileedit_bp = Blueprint('fileedit', __name__)

# 上传简历路由
@fileedit_bp.route('/upload_resume', methods=['POST'])
def upload_resume():
    if 'resumeFile' not in request.files or 'employeeName' not in request.form:
        return jsonify({'status': 'error', 'message': '简历上传失败：缺少文件或姓名'})

    resume_file = request.files['resumeFile']
    name = request.form['employeeName']

    if resume_file.filename == '':
        return jsonify({'status': 'error', 'message': '简历上传失败：未选择文件'})

    if not allowed_file(resume_file.filename):
        return jsonify({'status': 'error', 'message': '简历上传失败：文件类型不允许'})

    # 文件保存路径
    if not os.path.exists(STAFF_FILE_PATH):
        os.makedirs(STAFF_FILE_PATH)

    # 保存文件
    file_extension = os.path.splitext(resume_file.filename)[1]
    filename = name + file_extension
    file_path = os.path.join(STAFF_FILE_PATH, filename)
    resume_file.save(file_path)

    download_link = url_for('fileedit.download_resume', filename=filename, _external=True)

    resumes = load_resumes(CV_FILE)
    resumes[name] = {"filename": filename, "download_link": download_link}
    save_resumes(CV_FILE, resumes)

    return jsonify({'status': 'success', 'message': '简历上传成功'})

@fileedit_bp.route('/upload_resume_en', methods=['POST'])
def upload_resume_en():
    if 'resumeFile' not in request.files or 'employeeName' not in request.form:
        return jsonify({'status': 'error', 'message': '简历上传失败：缺少文件或姓名'})

    resume_file = request.files['resumeFile']
    name = request.form['employeeName']

    if resume_file.filename == '':
        return jsonify({'status': 'error', 'message': '简历上传失败：未选择文件'})

    if not allowed_file(resume_file.filename):
        return jsonify({'status': 'error', 'message': '简历上传失败：文件类型不允许'})

    # 保存文件
    file_extension = os.path.splitext(resume_file.filename)[1]
    filename = name + "_EN" + file_extension  # 使用姓名+_EN作为文件名
    file_path = os.path.join(STAFF_FILE_PATH, filename)
    resume_file.save(file_path)

    download_link = url_for('fileedit.download_resume', filename=filename, _external=True)

    # 更新或新增英文简历 JSON 数据
    resumes = load_resumes(CV_EN_FILE)
    resumes[name] = {"filename": filename, "download_link": download_link}
    save_resumes(CV_EN_FILE, resumes)

    return jsonify({'status': 'success', 'message': '简历上传成功'})


# 检查文件扩展名
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@fileedit_bp.route('/download_resume/<filename>')
def download_resume(filename):
    """简历下载功能"""
    file_path = os.path.join(STAFF_FILE_PATH, filename)
    if os.path.exists(file_path):
        return send_from_directory(STAFF_FILE_PATH, filename, as_attachment=True)
    else:
        flash('文件不存在', 'danger')
        return redirect(url_for('staffedit.employeeslist'))

@fileedit_bp.route('/csvdownload')
def csvdownload():
    user_id = session.get('user_id')
    if not user_id:
        return render_template('error.html', message='User not logged in'), 401
    user = User.query.get(user_id)
    if not user:
        return render_template('error.html', message='User not found'), 404
    return render_template('csvdownload.html', username=user.username)

@fileedit_bp.route('/preview_resume', methods=['POST'])
def preview_resume():
    name = request.form.get('name')
    language = request.form.get('language')  # Determine whether it's Chinese or English
    resumesCN = load_resumes(CV_FILE)
    resumesEN = load_resumes(CV_EN_FILE)
    if language == 'cn':
        if name in resumesCN:
            resume_path = resumesCN[name]['download_link']
        else:
            return jsonify(success=False, message="Resume not found")
    elif language == 'en':
        if name in resumesEN:
            resume_path = resumesEN[name]['download_link']
        else:
            return jsonify(success=False, message="Resume not found")
    else:
        return jsonify(success=False, message="Invalid language option")

    # Check if the file exists (if needed, depends on你的需求)
    if resume_path:
        return jsonify(success=True, resume_url=resume_path)
    else:
        return jsonify(success=False, message="Resume not found")

@fileedit_bp.route('/UpdateSkills', methods=['POST'])
def UpdateSkills():
    """
    使用示例
    """
    employee_name = request.form.get('name')  # Get the employee's name
    current_skills = request.form.get('skills')  # Get the existing skills data
    cvfile = employee_name+".docx"
    file_path = os.path.join(STAFF_FILE_PATH, cvfile)
    if os.path.exists(file_path):
        file_path = file_path
    else:
        pdfile = employee_name + ".pdf"
        file_path = os.path.join(STAFF_FILE_PATH, pdfile)
    text = extract_text_from_file(file_path)
    if text:
        query = f'''这个是该员工的简历信息：{text}
目前的技能标签为：{current_skills}。
若在简历中发现新技能，请添加上以如下格式技能1/技能2/技能3.
仅需回复 技能标签即可 即 {current_skills}/新增技能1/新增技能2/新增技能3 以原始技能标签开头的字符串'''
        messages = [{"role": "system", "content": "你是一名从简历中提取专业技能的工程师！"},
                    {"role": "user", "content": query}]
        new_skills = chat_mode_script(messages, stream=False)
        print(new_skills)
        return jsonify({
            'success': True,
            'new_skills': new_skills  # Send back the new skills
        })
    else:
        print("提取失败!")
        return jsonify({
            'success': False,
            'new_skills': ''  # Send back the new skills
        })


    # Here, you would process the employee's skills (e.g., run some analysis or get suggestions)
    # For example, let's assume the backend generates a new skill set for the employee


@fileedit_bp.route('/sysinfo')
def index():
    return render_template('ststeminfo.html')

@fileedit_bp.route('/api/resources')
def api_resources():
    try:
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        disk_usage = psutil.disk_usage('/')
        disk_usage_percent = disk_usage.percent
        return jsonify(cpu_usage=cpu_usage, memory_usage=memory_usage, disk_usage=disk_usage_percent)
    except Exception as e:
        return jsonify(error=str(e)), 500