from app import db

class Employee(db.Model):
    __bind_key__ = 'staff'  # 使用 staff 数据库
    __tablename__ = 'employees'
    employee_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    level = db.Column(db.String(20), nullable=True)
    location = db.Column(db.String(20), nullable=False)
    sex = db.Column(db.String(10), nullable=True)
    skill = db.Column(db.String(100), nullable=False)
    chai = db.Column(db.String(10), nullable=True)
    lang = db.Column(db.String(50), nullable=True)
    projects = db.relationship('ProjectEmployee', backref='employee', lazy='dynamic')

class Project(db.Model):
    # 定义表名
    __bind_key__ = 'staff'  # 使用 staff 数据库
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)  # 项目ID
    project_name = db.Column(db.String(100), nullable=False)  # 项目名称
    responsible_person = db.Column(db.String(100), nullable=False)  # 负责人
    implementation_period = db.Column(db.String(100), nullable=False)  # 实施周期
    location = db.Column(db.String(100), nullable=False)  # 地点
    remote_allowed = db.Column(db.Boolean, default=False)  # 接受远程
    language_requirement = db.Column(db.String(100), nullable=False)  # 语言要求
    required_number = db.Column(db.Integer, nullable=False)  # 需求人数
    notes = db.Column(db.Text, nullable=True)  # 备注
    employees = db.relationship('ProjectEmployee', backref='project', lazy='dynamic')

class ProjectEmployee(db.Model):
    __bind_key__ = 'staff'  # 使用 staff 数据库
    __tablename__ = 'project_employee'
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), primary_key=True)
    utilization = db.Column(db.Integer, nullable=False, default=0)  # 利用率字段，范围0-100
    schedule = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<ProjectEmployee {self.employee_id} - {self.project_id}>'