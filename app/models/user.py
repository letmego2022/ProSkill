import json
from app import db
from werkzeug.security import generate_password_hash, check_password_hash

class History(db.Model):
    __bind_key__ = 'user'  # 使用 user 数据库
    __tablename__ = 'history'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 外键字段
    messages = db.Column(db.Text)  # 存储 JSON 字符串的字段
    user = db.relationship('User', backref=db.backref('histories', lazy=True))  # 定义关系


class User(db.Model):
    __bind_key__ = 'user'  # 使用 user 数据库
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class TestResult(db.Model):
    __bind_key__ = 'test_case'  # 使用 test_case 数据库
    __tablename__ = 'test_results'
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255))
    test_res = db.Column(db.String(1))
    api_path = db.Column(db.String(255))
    test_outcome = db.Column(db.String(255))
    runs = db.Column(db.Integer)
    output = db.Column(db.Text)
    python_code = db.Column(db.Text)
    userid = db.Column(db.Integer)  # 注意这里的外键关系，如果有的话

class APIInfo(db.Model):
    __bind_key__ = 'gkinfo'  # 指定使用 gkinfo 数据库
    __tablename__ = 'api_info'
    id = db.Column(db.Integer, primary_key=True)
    api_info = db.Column(db.Text, nullable=False)  # 存储大文本的字段
    file_path = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return self.api_info