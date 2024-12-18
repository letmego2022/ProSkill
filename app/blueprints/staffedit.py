import pandas as pd
from flask import send_file,stream_with_context,session,Response, jsonify, Blueprint,render_template,request,redirect,url_for,flash
from app import db
import uuid
from app.models.user import User,History
from app.utils.api_utils import convert_date_range_to_string, compare_date_range, is_date_out_of_range
from app.models.staff import Employee, Project, ProjectEmployee
from config import CSV_FILE,PROJECT_FILE,CV_FILE, CV_EN_FILE
from datetime import datetime
from collections import defaultdict
from app.utils.utils import  chat_mode_staff,read_data
import json
from openpyxl import Workbook
import io

# 创建 Blueprint 实例
staffedit_bp = Blueprint('staffedit', __name__)
# Utility function to fetch current logged-in user
def get_logged_in_user():
    if 'logged_in' in session and session.get('logged_in'):
        user_id = session.get('user_id')
        return User.query.get(user_id)
    return None


def get_unique_locations():
    # 查询 Employee 表中唯一的 location 值
    locations = db.session.query(Employee.location).distinct().all()

    # 提取每个 location 值并将它们放入一个列表中
    location_list = [location[0] for location in locations]

    return location_list

def promdinfojsin():
    # 查询所有项目和员工关联数据
    projects = Project.query.all()

    # 创建一个嵌套的defaultdict来存储统计数据
    stats = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    # 创建一个字典来跟踪每个人在每个月的工作量分配
    person_allocation = defaultdict(lambda: defaultdict(float))

    for project in projects:
        # 获取与该项目关联的所有员工
        for project_employee in project.employees:
            employee = project_employee.employee

            # 获取员工的地点、当前任务排期、利用率等信息
            location = employee.location
            date_range = project_employee.schedule
            if "到" in date_range:
                utilization = float(project_employee.utilization) / 100  # 将利用率转换为小数
                name = employee.name

                # 解析日期范围
                start_date_str, end_date_str = date_range.split("到")
                start_date = datetime.strptime(start_date_str.strip(), "%Y-%m-%d")
                end_date = datetime.strptime(end_date_str.strip(), "%Y-%m-%d")

                # 统计每个月的人数，考虑利用率
                current_date = start_date
                while current_date <= end_date:
                    month_key = f"{current_date.year}-{current_date.month:02d}"

                    # 检查这个人在这个月的总工作量是否已经达到100%
                    current_allocation = person_allocation[name][month_key]
                    remaining_allocation = 1.0 - current_allocation

                    if remaining_allocation > 0:
                        # 只添加剩余的可用工作量
                        actual_utilization = min(utilization, remaining_allocation)
                        stats[project.project_name][location][month_key] += actual_utilization
                        person_allocation[name][month_key] += actual_utilization

                    # 移到下个月
                    if current_date.month == 12:
                        current_date = current_date.replace(year=current_date.year + 1, month=1)
                    else:
                        current_date = current_date.replace(month=current_date.month + 1)

    # 构建JSON格式的统计结果
    result = {}
    for project in stats:
        result[project] = {}
        for location in stats[project]:
            result[project][location] = {}
            for month, count in sorted(stats[project][location].items()):
                # 四舍五入到1位小数
                result[project][location][month] = round(count, 1)

    # 返回结果
    return json.dumps(result, ensure_ascii=False, indent=2)

def get_projects_data():
    # 查询所有项目及其员工信息
    result = []
    for project in Project.query.all():
        project_info = {
            'project_id': project.id,
            'project_name': project.project_name,
            'responsible_person': project.responsible_person,
            'implementation_period': project.implementation_period,
            'location': project.location,
            'remote_allowed': project.remote_allowed,
            'language_requirement': project.language_requirement,
            'required_number': project.required_number,
            'notes': project.notes,
            'employees': []
        }

        # 获取该项目下的所有员工信息（从 ProjectEmployee 中获取）
        for project_employee in project.employees:
            employee = project_employee.employee
            employee_info = {
                'employee_id': employee.employee_id,
                # 'name': employee.name,
                # 'level': employee.level,
                # 'location': employee.location,
                # 'sex': employee.sex,
                # 'skill': employee.skill,
                # 'chai': employee.chai,
                # 'lang': employee.lang,
                'utilization': project_employee.utilization,
                'schedule': project_employee.schedule
            }
            project_info['employees'].append(employee_info)

        result.append(project_info)

    return result

def search_projects_by_name(project_name):
    # 查询所有项目及其员工信息
    result = []
    for project in Project.query.filter(Project.project_name.like(f'%{project_name}%')).all():
        project_info = {
            'project_id': project.id,
            'project_name': project.project_name,
            'responsible_person': project.responsible_person,
            'implementation_period': project.implementation_period,
            'location': project.location,
            'remote_allowed': project.remote_allowed,
            'language_requirement': project.language_requirement,
            'required_number': project.required_number,
            'notes': project.notes,
            'employees': []
        }

        # 获取该项目下的所有员工信息（从 ProjectEmployee 中获取）
        for project_employee in project.employees:
            employee = project_employee.employee
            employee_info = {
                'employee_id': employee.employee_id,
                'name': employee.name,
                'level': employee.level,
                'location': employee.location,
                'sex': employee.sex,
                'skill': employee.skill,
                'chai': employee.chai,
                'lang': employee.lang,
                'utilization': project_employee.utilization,
                'schedule': project_employee.schedule
            }
            project_info['employees'].append(employee_info)

        result.append(project_info)

    return result

def get_project_status(start_date, end_date):
    """计算项目的状态"""
    today = datetime.now().date()
    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    if today < start_date:
        return "未开始"
    elif today > end_date:
        return "已结束"
    else:
        # 计算剩余天数
        delta = end_date - today
        if delta.days < 14:
            return "剩余不到14天"
        else:
            return "进行中"

def read_and_parse_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        print(f"错误：文件 {file_path} 未找到。")
    except json.JSONDecodeError:
        print(f"错误：文件 {file_path} 不是有效的JSON文件。")
    except Exception as e:
        print(f"发生错误：{e}")

def get_employees_data():
    # 查询所有员工及其项目信息
    result = []
    for employee in Employee.query.all():
        employee_info = {
            'employee_id': employee.employee_id,
            'name': employee.name,
            'level': employee.level,
            'location': employee.location,
            'sex': employee.sex,
            'skill': employee.skill,
            'chai': employee.chai,
            'lang': employee.lang,
            'projects': []
        }
        for project_employee in employee.projects:
            project = project_employee.project
            project_info = {
                'project_name': project.project_name,
                'utilization': project_employee.utilization,
                'implementation_period': project_employee.schedule
            }
            employee_info['projects'].append(project_info)
        result.append(employee_info)
    return result


def search_employees_by_location(location):
    # 查询员工所在的地点
    employees = Employee.query.filter(Employee.location.like(f'%{location}%')).all()

    employee_info = []
    for employee in employees:
        employee_data = {
            'employee_id': employee.employee_id,
            'name': employee.name,
            'level': employee.level,
            'location': employee.location,
            'sex': employee.sex,
            'skill': employee.skill,
            'chai': employee.chai,
            'lang': employee.lang,
            'projects': []  # 可根据需求加入员工参与的项目数据
        }

        # 可选择将员工参与的项目信息也添加进来
        for project_employee in employee.projects:
            project = project_employee.project
            project_info = {
                'project_name': project.project_name,
                'utilization': project_employee.utilization,
                'schedule': project_employee.schedule
            }
            employee_data['projects'].append(project_info)

        employee_info.append(employee_data)

    return employee_info


# 主要函数：处理人员信息并比较日期
def process_date_ranges(needskilllist, renyuanxinxi, start1, end1, location):
    """
    处理人员信息字符串，比较每个日期范围与给定的日期范围是否冲突。

    参数:
    needskilllist (list): 需要的技能列表，例如 ["手动测试"]。
    renyuanxinxi (list): 包含人员信息的列表，每个元素是一个字典，包含员工信息和项目数据。
    start1 (str): 比较的开始日期，格式为"YYYY-MM-DD"。
    end1 (str): 比较的结束日期，格式为"YYYY-MM-DD"。
    location (str): 比较的地点。

    返回:
    list: 处理后的人员信息，每个员工的条目包含原始信息和日期冲突结果。
    """
    output_lines = []

    # 遍历每个员工信息
    for employee in renyuanxinxi:
        name = employee["name"]
        level = employee["level"]
        locationtmp = employee["location"]
        skills = employee["skill"].split("/")  # 技能列表
        chai = employee["chai"]
        lang = employee["lang"]
        projects = employee.get("projects", [])

        # 将技能列表转换为集合，进行比对
        set1 = set(skills)
        set2 = set(needskilllist)

        # 检查技能是否匹配
        if not set1.isdisjoint(set2):
            if "是" == chai or location == locationtmp:  # 如果匹配技能且地点或“茶”条件满足
                if projects:  # 如果有项目
                    for project in projects:
                        project_name = project["project_name"]
                        date_range = project.get("implementation_period", "")

                        if "到" in date_range:  # 确保日期范围有效
                            base_start, base_end = convert_date_range_to_string(date_range)
                            if base_start and base_end:  # 确保日期转换成功

                                # 比较日期范围是否冲突
                                result = compare_date_range(start1, end1, base_start, base_end)
                                output_lines.append(
                                    f"姓名：{name} 职级：{level} base：{locationtmp} 拥有技能：{employee['skill']} 语言能力：{lang} 目前项目：{project_name} / {result}"
                                )
                        else:
                            output_lines.append(
                                f"姓名：{name} 职级：{level} base：{locationtmp} 拥有技能：{employee['skill']} 语言能力：{lang} 目前项目：{project_name} / 无有效日期"
                            )
                else:  # 如果没有项目
                    output_lines.append(
                        f"姓名：{name} 职级：{level} base：{locationtmp} 拥有技能：{employee['skill']} 语言能力：{lang} 目前项目：无项目"
                    )

    # 返回所有员工信息的字符串
    return "\n".join(output_lines)



def process_date_ranges_false(needskilllist, renyuanxinxi, start1, end1, location):
    """
    处理人员信息，返回符合技能和地点要求的所有员工信息。

    参数:
    needskilllist (list): 需要的技能列表，例如 ["手动测试"]。
    renyuanxinxi (list): 包含人员信息的列表，每个元素是一个字典，包含员工信息和项目数据。
    start1 (str): 比较的开始日期，格式为"YYYY-MM-DD"（虽然这里不做日期冲突判断，但保留此参数）。
    end1 (str): 比较的结束日期，格式为"YYYY-MM-DD"（同上）。
    location (str): 比较的地点。

    返回:
    str: 处理后的字符串，包含原始信息和项目详情，每条记录之间用换行符分隔。
    """
    output_lines = []

    # 遍历每个员工信息
    for employee in renyuanxinxi:
        name = employee["name"]
        level = employee["level"]
        locationtmp = employee["location"]
        skills = employee["skill"].split("/")  # 技能列表
        chai = employee["chai"]
        lang = employee["lang"]
        projects = employee.get("projects", [])

        # 将技能列表转换为集合，进行比对
        set1 = set(skills)
        set2 = set(needskilllist)

        # 检查技能是否匹配
        if not set1.isdisjoint(set2):
            if "是" == chai or location == locationtmp:  # 如果匹配技能且地点或“茶”条件满足
                if projects:  # 如果有项目
                    for project in projects:
                        project_name = project["project_name"]
                        date_range = project.get("implementation_period", "")

                        # 拼接员工信息和项目信息
                        output_lines.append(
                            f"姓名：{name} 职级：{level} base：{locationtmp} 拥有技能：{employee['skill']} 语言能力：{lang} 目前项目：{project_name} / 日期范围：{date_range if date_range else '无日期'}"
                        )
                else:  # 如果没有项目
                    output_lines.append(
                        f"姓名：{name} 职级：{level} base：{locationtmp} 拥有技能：{employee['skill']} 语言能力：{lang} 目前项目：无项目"
                    )

    # 返回所有员工信息的字符串
    return "\n".join(output_lines)


@staffedit_bp.route('/download_employees_data', methods=['GET'])
def download_employees_data():
    # 获取所有员工数据
    result = get_employees_data()

    # 创建一个新的Excel工作簿
    wb = Workbook()
    ws = wb.active
    ws.title = "Employees Data"

    # 写入表头
    headers = [
        'employee_id', 'name', 'level', 'location', 'sex', 'skill', 'chai', 'lang',
        'project_name', 'utilization', 'implementation_period'
    ]
    ws.append(headers)

    # 写入员工数据
    for employee in result:
        for project in employee['projects']:
            row = [
                employee['employee_id'],
                employee['name'],
                employee['level'],
                employee['location'],
                employee['sex'],
                employee['skill'],
                employee['chai'],
                employee['lang'],
                project['project_name'],
                project['utilization'],
                project['implementation_period']
            ]
            ws.append(row)

    # 将Excel文件保存到内存
    output = io.BytesIO()
    wb.save(output)

    # 移动游标到文件的开头
    output.seek(0)

    # 返回生成的xlsx文件供下载
    return send_file(output, as_attachment=True, download_name='employees_data.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
# 定义创建数据库并导入函数
@staffedit_bp.route('/stafftoinstall', methods=['GET', 'POST'])
def import_employees_from_csv():
    db.create_all()  # 创建表
    # 读取员工CSV文件
    csv_file_path = CSV_FILE
    df_employees = pd.read_csv(csv_file_path)

    # 遍历每一行员工数据并插入到数据库
    for index, row in df_employees.iterrows():
        employee = Employee(
            name=row['姓名'],
            level=row['职级'],
            location=row['地点'],
            sex=row['性别'],
            skill=row['专业技能'],
            chai=row['接收出差'] == '是',
            lang=row['语言能力'],
        )
        db.session.add(employee)

    # 提交所有员工
    db.session.commit()

    # 读取项目CSV文件
    project_file_path = PROJECT_FILE
    df_projects = pd.read_csv(project_file_path)

    # 遍历每一行项目数据并插入到数据库
    for index, row in df_projects.iterrows():
        project = Project(
            project_name=row['项目名称'],
            responsible_person=row['负责人'],
            implementation_period=row['实施周期'],
            location=row['地点'],
            remote_allowed=row['接受远程'] == '是',
            language_requirement=row['语言能力'],
            required_number=row['需求人数'],
            notes=row['备注']
        )
        db.session.add(project)

    # 提交所有项目
    db.session.commit()

    # 处理员工和项目的关联以及利用率
    for index, row in df_employees.iterrows():
        # 假设CSV中有一个字段'当前项目'包含项目名称，'Utilization'包含利用率
        project_name = row['当前项目']
        utilization = row['Utilization']
        schedule = row['当前任务排期']

        # 根据项目名称查找项目ID
        project = Project.query.filter_by(project_name=project_name).first()
        if project:
            # 根据员工姓名查找员工ID
            employee = Employee.query.filter_by(name=row['姓名']).first()
            if employee:
                # 创建关联对象
                project_employee = ProjectEmployee(
                    employee_id=employee.employee_id,
                    project_id=project.id,
                    utilization=utilization,
                    schedule=schedule
                )
                db.session.add(project_employee)

    # 提交所有关联对象
    db.session.commit()

    return jsonify({'message': 'Data imported successfully'})


@staffedit_bp.route('/projects')
def projects():
    projects = Project.query.all()  # 查询所有项目
    return render_template('projects.html', projects=projects)

@staffedit_bp.route('/projects/<int:project_id>/details')
def project_details(project_id):
    project = Project.query.get_or_404(project_id)  # 根据项目ID查询项目
    all_employees = Employee.query.all()
    project_employees = ProjectEmployee.query.filter_by(project_id=project_id).all()  # 查询项目相关的所有ProjectEmployee对象
    employees = [Employee.query.get(pe.employee_id) for pe in project_employees]  # 通过employee_id查询每个员工的详细信息
    return render_template('project_details.html', project=project, employees=employees,all_employees=all_employees)


@staffedit_bp.route('/add_project', methods=['POST'])
def add_project():
    project_name = request.form['project_name']
    responsible_person = request.form['responsible_person']
    implementation_period = request.form['implementation_period']
    location = request.form['location']
    remote_allowed = request.form['remote_allowed'] == 'True'
    language_requirement = request.form['language_requirement']
    required_number = int(request.form['required_number'])
    notes = request.form['notes']

    # 创建新项目
    new_project = Project(
        project_name=project_name,
        responsible_person=responsible_person,
        implementation_period=implementation_period,
        location=location,
        remote_allowed=remote_allowed,
        language_requirement=language_requirement,
        required_number=required_number,
        notes=notes
    )
    db.session.add(new_project)
    db.session.commit()
    flash('项目添加成功！')
    return redirect(url_for('staffedit.projects'))

@staffedit_bp.route('/editEmployee/<int:employee_id>', methods=['GET'])
def edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    return render_template('edit_employee.html', employee=employee)

@staffedit_bp.route('/employees/<int:employee_id>/update', methods=['POST'])
def update_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    form = request.form

    # Update employee details based on form data
    employee.name = form['name']
    employee.level = form['level']
    employee.location = form['location']
    employee.sex = form['sex']
    employee.skill = form['skill']
    employee.chai = form['chai']  # Assuming 'chai' represents willingness to travel, adjust as needed
    employee.lang = form['lang']

    # Commit the changes to the database
    db.session.commit()
    flash('员工信息更新成功！')
    return redirect(url_for('staffedit.employeeslist'))  #
# 修改项目
@staffedit_bp.route('/projects/<int:project_id>/edit', methods=['GET'])
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    return render_template('edit_project.html', project=project)


@staffedit_bp.route('/projects/<int:project_id>/update', methods=['POST'])
def update_project(project_id):
    project = Project.query.get_or_404(project_id)
    form = request.form
    project.project_name = form['project_name']
    project.responsible_person = form['responsible_person']
    project.implementation_period = form['implementation_period']
    project.location = form['location']
    project.remote_allowed = form['remote_allowed'] == 'True'  # 确保将字符串转换为布尔值
    project.language_requirement = form['language_requirement']
    project.required_number = int(form['required_number'])  # 确保将字符串转换为整数
    project.notes = form['notes']

    # 执行数据库更新操作
    db.session.commit()
    flash('项目更新成功！')
    return redirect(url_for('staffedit.projects'))

# 删除项目
@staffedit_bp.route('/projects_remove', methods=['POST'])
def delete_project():
    # 删除项目的逻辑
    data = request.get_json()
    project_id = data['project_id']
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    return jsonify({'message': 'Project removed successfully'}), 200

@staffedit_bp.route('/projects_remove_employee', methods=['POST'])
def remove_employee():
    # 获取 JSON 数据
    data = request.get_json()

    # 验证请求数据
    if not data or 'employee_id' not in data or 'project_id' not in data:
        return jsonify({'error': 'Invalid request data'}), 400

    employee_id = data['employee_id']
    project_id = data['project_id']

    # 查找项目和员工
    project = Project.query.get_or_404(project_id)
    employee = Employee.query.get_or_404(employee_id)

    # 查找项目和员工之间的关联记录
    project_employee = ProjectEmployee.query.filter_by(project_id=project.id, employee_id=employee.employee_id).first()

    # 如果找到关联记录，则删除它
    if project_employee:
        db.session.delete(project_employee)
        db.session.commit()
        return jsonify({'message': 'Employee removed successfully from project'}), 200
    else:
        # 如果没有找到关联记录，返回 404 Not Found
        return jsonify({'error': 'Employee not found in project'}), 404
    # 执行移除员工的逻辑，比如移除员工与项目的关联

@staffedit_bp.route('/add_employee_to_project', methods=['POST'])
def add_employee_to_project():
    data = request.get_json()

    # 验证请求数据
    if not data or 'project_id' not in data or 'employee_id' not in data or 'utilization' not in data or 'schedule' not in data:
        return jsonify({'error': 'Invalid request data'}), 400

    project_id = data['project_id']
    employee_id = data['employee_id']
    utilization = data['utilization']
    schedule = data['schedule']

    # 查找项目和员工
    project = Project.query.get_or_404(project_id)
    employee = Employee.query.get_or_404(employee_id)

    # 查找项目和员工之间的关联记录
    project_employee = ProjectEmployee.query.filter_by(project_id=project.id, employee_id=employee.employee_id).first()

    if not project_employee:
        new_project_employee = ProjectEmployee(
            project_id=project.id,
            employee_id=employee.employee_id,
            utilization=utilization,
            schedule=schedule
        )
        db.session.add(new_project_employee)
        db.session.commit()
        return jsonify({'message': 'Employee added to project successfully'}), 201
    else:
        return jsonify({'error': 'Employee already exists in project'}), 400


@staffedit_bp.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        # 如果是 POST 请求，处理表单提交
        # 获取表单数据
        name = request.form.get('name')
        level = request.form.get('level')
        location = request.form.get('location')
        sex = request.form.get('sex')
        skill = request.form.get('skill')
        chai = request.form.get('chai') == 'True'  # 将字符串转换为布尔值
        lang = request.form.get('lang')

        # 创建新的员工对象
        new_employee = Employee(
            name=name,
            level=level,
            location=location,
            sex=sex,
            skill=skill,
            chai=chai,
            lang=lang
        )
        db.session.add(new_employee)
        db.session.commit()
        flash('添加员工成功！')
        return redirect(url_for('staffedit.projects'))


@staffedit_bp.route('/employees_data')
def employees_data():
    return jsonify(get_employees_data())

@staffedit_bp.route('/employeeslist')
def employeeslist():
    return render_template('employeeslist.html')  # 渲染前端页面


@staffedit_bp.route('/employees/<int:employee_id>', methods=['DELETE'])
def delete_employee(employee_id):
    # 首先尝试获取员工
    employee = Employee.query.get(employee_id)
    if employee:
        # 删除与员工关联的项目人员关系记录
        project_employees = ProjectEmployee.query.filter_by(employee_id=employee_id).all()
        for project_employee in project_employees:
            db.session.delete(project_employee)
        db.session.commit()  # 提交项目人员关系记录的删除操作

        # 删除员工
        db.session.delete(employee)
        db.session.commit()
        return jsonify({'message': '员工删除成功'}), 200
    else:
        return jsonify({'message': '员工未找到'}), 404

@staffedit_bp.route('/employeesinfonew', methods=['GET'])
def get_employeesinfonew():
    employeesinfo = []
    employeeslist = []
    employees = get_employees_data()
    #{'employee_id': 57, 'name': '孙明明', 'level': 'B2', 'location': '上海', 'sex': '男', 'skill': '自动化测试/Java开发/接口测试/性能测试/持续集成/项目管理/团队管理/需求分析/测试用例设计/缺陷管理/测试框架搭建/测试工具开发/版本控制/Jenkins部署/SpringBoot/SpringCloud/Mybatis/Mysql/Nacos/单元测试/代码审查/技术文档编写', 'chai': '0', 'lang': None, 'projects': [{'project_name': 'OCBC-CBS UAT', 'utilization': 100, 'implementation_period': '2024-11-25到2025-06-24'}]},
    for staff in employees:
        if staff['projects']:
            for project in staff['projects']:
                if "到" in project['implementation_period']:
                    start_date_str, end_date_str = project['implementation_period'].split("到")
                    tmpinfo = {
                        "location": staff.get('location'),
                        "name": staff.get("name"),
                        "skills": (staff.get("skill") or "").split('/'),
                        "languages": (staff.get("lang") or "").split('/'),
                        "isFree": is_date_out_of_range(start_date_str, end_date_str),
                        "acceptsTravel": (staff.get("chai") == "1"),
                    }
                    stat = get_project_status(start_date_str, end_date_str)
                    if stat == "已结束":
                        staffinfo = {
                            "name": staff["name"],
                            "rank": staff["level"],
                            "location": staff["location"],
                            "currentProject": project["project_name"],
                            "taskSchedule": project["implementation_period"],
                            "status": "空闲"
                        }
                        employeeslist.append(staffinfo)
                    elif stat == "剩余不到14天":
                        staffinfo = {
                            "name": staff["name"],
                            "rank": staff["level"],
                            "location": staff["location"],
                            "currentProject": project["project_name"],
                            "taskSchedule": project["implementation_period"],
                            "status": "剩余不到14天"
                        }
                        employeeslist.append(staffinfo)
                    employeesinfo.append(tmpinfo)
                elif "长期" in project['implementation_period']:
                    tmpinfo = {
                        "location": staff.get('location'),
                        "name": staff.get("name"),
                        "skills": (staff.get("skill") or "").split('/'),
                        "languages": (staff.get("lang") or "").split('/'),
                        "isFree": False,
                        "acceptsTravel": (staff.get("chai") == "1"),
                    }
                    employeesinfo.append(tmpinfo)
        else:
            tmpinfo = {
                "location": staff.get('location'),
                "name": staff.get("name"),
                "skills": (staff.get("skill") or "").split('/'),
                "languages": (staff.get("lang") or "").split('/'),
                "isFree": True,
                "acceptsTravel": (staff.get("chai") == "1"),
            }
            staffinfo = {
                "name": staff["name"],
                "rank": staff["level"],
                "location": staff["location"],
                "currentProject": "无项目",
                "taskSchedule": "无排期",
                "status": "空闲"
            }
            employeeslist.append(staffinfo)
            employeesinfo.append(tmpinfo)
    # 数据分析
    location_count = {}
    is_free_count = {"True": 0, "False": 0}
    # 使用字典来存储已经见过的name
    seen = {}
    unique_employeesinfo = []

    for person in employeesinfo:
        if person['name'] not in seen:
            seen[person['name']] = True
            unique_employeesinfo.append(person)

    for person in unique_employeesinfo:
        # print(person)
        location_count[person["location"]] = location_count.get(person["location"], 0) + 1
        is_free_count[str(person["isFree"])] += 1
    data2 = get_projects_data()
    project_data = []
    full = 0
    incomplete = 0
    for pro in data2:
        if pro['required_number'] == len(pro['employees']):
            full = full + 1
        else:
            incomplete = incomplete + 1
        if "到" in pro['implementation_period']:
            start_date_str, end_date_str = pro['implementation_period'].split("到")
            prot = {"name": pro['project_name'], "manager":pro['responsible_person'], "location": pro['location'], "start_date": start_date_str,
                    "end_date": end_date_str, "status": ""}
            project_data.append(prot)
        else:
            pass
            # prot = {"name": tmp[0], "start_date": "-", "end_date": "-", "status": "暂停"}

    for project in project_data:
        if project["status"] == "":
            project["status"] = get_project_status(project["start_date"], project["end_date"])
    # 返回 JSON 数据
    # 过滤出状态为“剩余不到14天”的项目
    projects_less_than_14_days = [project for project in project_data if project["status"] == "剩余不到14天"]
    return jsonify({
        "location_count": location_count,
        "is_free_count": is_free_count,
        "projects": projects_less_than_14_days,
        "project_status": {
            "full": full,
            "incomplete": incomplete
        },
        "employees": employeeslist
    })

@staffedit_bp.route('/projectdetailsnew', methods=['GET', 'POST'])
def get_project_details():
    data = request.get_json()
    project_name = data.get('name')
    lender = data.get('lender')
    project = search_projects_by_name(project_name)[0]
    employees = []
    for pepl in project['employees']:
        start_date_str, end_date_str = pepl["schedule"].split("到")
        tmpinfo = {
            "name": pepl["name"],
            "skills": (pepl["skill"] or "").split('/'),
            "languages": (pepl["lang"] or "").split('/'),
            "isFree": is_date_out_of_range(start_date_str, end_date_str),
            "acceptsTravel": (pepl["chai"]  == "1"),
        }
        employees.append(tmpinfo)
    if employees:
        ss = {
            "name": project_name,
            "lender": lender,
            "team_size": len(employees),
            "members": employees,
        }
        return jsonify(ss)
    else:
        return jsonify({"error": "Project not found"}), 404

@staffedit_bp.route('/employeesnew', methods=['GET'])
def get_employees():
    location = request.args.get('location')
    stainfo = search_employees_by_location(location)
    # 提取所有的月份
    employees = []
    for pepl in stainfo:
        if pepl['projects']:
            for pro in pepl['projects']:
                start_date_str, end_date_str = pro["schedule"].split("到")
                tmpinfo = {
                    "name": pepl["name"],
                    "skills": (pepl["skill"] or "").split('/'),
                    "languages": (pepl["lang"] or "").split('/'),
                    "isFree": is_date_out_of_range(start_date_str, end_date_str),
                    "acceptsTravel": (pepl["chai"] == "1"),
                }
                employees.append(tmpinfo)
        else:
            tmpinfo = {
                "name": pepl["name"],
                "skills": (pepl["skill"] or "").split('/'),
                "languages": (pepl["lang"] or "").split('/'),
                "isFree": True,
                "acceptsTravel": (pepl["chai"] == "1"),
            }
            employees.append(tmpinfo)
    # 可以根据 `location` 过滤返回数据
    return jsonify(employees)

@staffedit_bp.route('/proDashboardnew')
def proDashboard():
    user_id = session.get('user_id')
    if not user_id:
        return render_template('error.html', message='User not logged in'), 401
    user = User.query.get(user_id)
    if not user:
        return render_template('error.html', message='User not found'), 404

    # 提取所有的月份
    data = json.loads(promdinfojsin())  # 通过调用promdinfojsin来获取项目数据
    months = set()
    for project in data.values():
        for location in project.values():
            months.update(location.keys())

    # 按月份升序排序
    sorted_months = sorted(months)

    # 返回渲染模板
    return render_template('projectdas.html', username=user.username, months=sorted_months)

@staffedit_bp.route('/api/project_manpowernew', methods=['GET'])
def projectsheet():
    try:
        data = promdinfojsin()  # 获取人力投入数据
        return jsonify(json.loads(data)), 200  # 注意这里需要用 json.loads() 转换成字典
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@staffedit_bp.route('/reset_renli_new', methods=['POST'])
def reset_renli():
    __bind_key__ = 'user'  # 使用 user 数据库
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401
    node_data_store = read_data()
    initial_history = [{"role": "system", "content": node_data_store.get("prompt31", "")}]
    new_history_entry = History(user_id=user_id, session_id=str(uuid.uuid4()), messages=json.dumps(initial_history))
    db.session.add(new_history_entry)
    db.session.commit()

    return jsonify({"message": "Session Reset Successful"}), 200

@staffedit_bp.route('/reset_pepo_new', methods=['POST'])
def reset_pepo():
    __bind_key__ = 'user'  # 使用 user 数据库
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401
    node_data_store = read_data()
    initial_history = [{"role": "system", "content": node_data_store.get("prompt32", "")}]
    new_history_entry = History(user_id=user_id, session_id=str(uuid.uuid4()), messages=json.dumps(initial_history))
    db.session.add(new_history_entry)
    db.session.commit()

    return jsonify({"message": "Session Reset Successful"}), 200

@staffedit_bp.route('/projectrequestnew', methods=['POST'])
def projectrequest():
    # 从文件中读取节点的可编辑内容
    node_data_store = read_data()
    data = request.get_json()  # Get the JSON data from the request body
    employees = data.get('employees', [])
    user = get_logged_in_user()
    if not user:
        return jsonify({'error': 'User not logged in'}), 403
    # {'acceptsTravel': False, 'isFree': False, 'languages': [''], 'name': '庞国强', 'skills': ['手动测试']}
    Selected_staff = "需要进行匹配项目的人员有：\n"
    for staff in employees:
        # 优化后的单行f-string格式化
        description = f"姓名：{staff['name']},工作技能有{str(staff['skills'])},语言能力有{str(staff['languages'])}，{'接受出差' if staff['acceptsTravel'] else '不接受出差'}，{'目前空闲' if staff['isFree'] else '目前繁忙，无法排遣项目'} \n"
        Selected_staff = Selected_staff + description
    proinfo_info =  get_projects_data()
    prostr = "缺额的项目信息如下:\n"
    for i in proinfo_info:
        quege = i['required_number'] - len(i['employees'])
        if quege > 0:
            proinfostr = f"{i['project_name']}项目目前存在人员缺额,负责人：{i['responsible_person']},目前缺少{quege}个人,实施周期为{i['implementation_period']},主要实施地点为{i['location']},是否可远程办公:{i['remote_allowed']},语言要求如下:{i['language_requirement']},备注信息:{i['notes']}\n"
        else:
            proinfostr = f"{i['project_name']}项目目前满员无缺额,负责人{i['responsible_person']},实施周期为{i['implementation_period']},主要实施地点为{i['location']},是否可远程办公:{i['remote_allowed']},语言要求如下:{i['language_requirement']},备注信息:{i['notes']}\n"
        prostr = prostr + proinfostr
#     resback = f'''回答要求:仅需回复markdown即可
# ```markdown
# ### 首要推荐
# | 项目 | 负责人 | 地点 | 实施周期 | 技能、语言匹配度 | 其他信息 |
# 请在此处填写推荐信息,必须在有人员缺额的项目中进行匹配,实施地点满足需求,技能匹配 即可推荐. 技能、语言匹配度中仅需要生命技能、语言匹配程度即可。其他信息中填写项目接受远程：√或者×，人员接受出差：√或者×
# ### 其他不完全匹配项目
# | 项目 | 负责人 | 地点 | 实施周期 | 技能、语言匹配度 | 其他信息 |
# 请在此处填写其他不完全匹配项目,人员缺额的其他项目放在这个位置中填入,满员无缺额项目中技能地点匹配的的也填入,如果没有合适的填入1-2个地点符合的项目。
# ```'''
    postai = Selected_staff + prostr + node_data_store.get("prompt321", "")

    def generate():
        # yield "\n 正在对需求进行分析⏳...\n"
        collected_messages = []
        for chunk in chat_mode_staff(postai, stream=True):
            yield chunk
            collected_messages.append(chunk)

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@staffedit_bp.route('/staffrequest_new', methods=['POST'])
def staffrequest():
    # 从文件中读取节点的可编辑内容
    node_data_store = read_data()
    data = request.get_json()  # Get the JSON data from the request body
    # query1 = data.get('query', '')  # Extract the 'query' field from the JSON data
    user = get_logged_in_user()
    # print(data)
    pnum = data.get('numPeople', '无要求')
    location = data.get('location', '无要求')
    languages = data.get('languages', '中文')
    if languages:
        languages = languages
    else:
        languages = "无语言要求"
    skills = data.get('skills', '无要求')
    otherInfo = data.get('otherInfo', '无')
    end = data.get('endTime', '2024-01-01')
    start = data.get('startTime', '2024-01-01')
    considerSchedule = data.get('considerSchedule', '')
    staff_info = get_employees_data()
    print(skills, start, end, location)
    # start, end = convert_date_range_to_string(implementationTime, 2024)
    if considerSchedule:
        result_string = process_date_ranges(skills, staff_info, start, end, location)
    else:
        result_string = process_date_ranges_false(skills, staff_info, start, end, location)
    Project_Info = f"新增项目：需要在{location}进行实施，实施时间为：{start}到{end}。需要具备以下技能{str(skills)}和语言能力{str(languages)}。共需人数为{pnum}，其他信息有{otherInfo}。当前的人员信息为{result_string}"
#     resback = f'''回答要求:仅需回复markdown即可
# ```markdown
# ### 完全匹配人员
# | 姓名 | 职级 | 地点 | 标签 | 当前项目 | 当前排期 | 技能匹配度 | 语言匹配度 | 排期冲突及解决方案 |
# 请在此处填写各项完全匹配人员，首先保障所选人员地点必须在{location}，然后是至少具备以下技能{str(skills)}和{str(languages)}语言能力！,排期冲突的话给出解决方案。
# 如果不存在完全匹配的人员则不用填写，人数不要超过{pnum}。
# ### 部分匹配推荐人员
# | 姓名 | 职级 | 地点 | 标签 | 当前项目 | 当前排期 | 技能匹配度 | 语言匹配度 | 排期冲突及解决方案 |
# 请在此处填写部分匹配推荐人员
# 地点符合推荐2人，排期符合推荐2人。当无完全匹配人员的时候适当增多。```
#     '''
    resback = f'{node_data_store.get("prompt311", "")}'
    if not user:
        return jsonify({'error': 'User not logged in'}), 403

    def generate():
        # yield "\n 正在对需求进行分析⏳...\n"
        collected_messages = []
        for chunk in chat_mode_staff(Project_Info + resback, stream=True):
            yield chunk
            collected_messages.append(chunk)
        result = ''.join(collected_messages)
        # yield "-- 获取简历🔄~~~"
        cv_info = read_and_parse_json(CV_FILE)
        cv_en_info = read_and_parse_json(CV_EN_FILE)
        cvpostinfp = '''
```markdown
'''
        for name in cv_info.keys():
            if name in result:
                tmp = f'''- **{name}:中文简历**: [{cv_info[name]["filename"]}]({cv_info[name]["download_link"]})'''
                cvpostinfp = cvpostinfp + tmp
                # yield tmp
            else:
                pass
        for name in cv_en_info.keys():
            if name in result:
                tmp = f'''- **{name}:英文简历**: [{cv_en_info[name]["filename"]}]({cv_en_info[name]["download_link"]})'''
                cvpostinfp = cvpostinfp + tmp
                # yield tmp
            else:
                pass
        cvpostinfp = cvpostinfp + '''
```
'''
        yield cvpostinfp
        # yield "\n 无对应简历"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@staffedit_bp.route('/demo1')
def demo1():
    user_id = session.get('user_id')
    if not user_id:
        return render_template('error.html', message='User not logged in'), 401
    user = User.query.get(user_id)
    if not user:
        return render_template('error.html', message='User not found'), 404
    return render_template('staffArrangement.html', username=user.username)


@staffedit_bp.route('/demo2')
def demo2():
    user_id = session.get('user_id')
    if not user_id:
        return render_template('error.html', message='User not logged in'), 401
    user = User.query.get(user_id)
    if not user:
        return render_template('error.html', message='User not found'), 404
        # 示例地点列表
    locations = get_unique_locations()

    return render_template(
        'projectArrangement.html',
        username=user.username,
        locations=locations  # 将地点列表传递到模板
    )
