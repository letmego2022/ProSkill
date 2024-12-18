# app/blueprints/dashboard.py
from flask import Blueprint,jsonify,request,render_template,redirect,url_for,session,flash
from app.utils.utils import read_data,write_data
from app.models.user import User

# 创建 Blueprint 实例
flow_bp = Blueprint('flow', __name__)


@flow_bp.route('/flowdesigner')
def flowdesignerforManual():
    if 'logged_in' in session and session.get('logged_in'):
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        if user:
            return render_template('flow_m.html',username=user.username)
        else:
            flash('用户未找到')
            return redirect(url_for('auth.login'))
    else:
        flash('未登录，请先登录')
        return redirect(url_for('auth.login'))

@flow_bp.route('/flowchart_m')
def flowchart_m():
    # 从文件中读取节点的可编辑内容
    node_data_store = read_data()

    # 节点的 label 是固定的，内容从 JSON 文件中读取
    flow_data = {
        "nodes": [
            {"id": "start", "label": "开始", "editable": False},
            {"id": "prompt31", "label": "项目需求匹配prompt", "editable": True, "content": node_data_store.get("prompt31", "")},
            {"id": "prompt311", "label": "项目需求回复要求", "editable": True,"content": node_data_store.get("prompt311", "")},
            {"id": "userinput", "label": "用户输入", "editable": False},
            {"id": "prompt32", "label": "人力资源分配prompt", "editable": True, "content": node_data_store.get("prompt32", "")},
            {"id": "prompt321", "label": "人力资源回复要求", "editable": True,
             "content": node_data_store.get("prompt321", "")},
            {"id": "programme", "label": "生成方案", "editable": False},
        ],
        "links": [
            {"source": "start", "target": "prompt31"},
            {"source": "start", "target": "prompt32"},
            {"source": "prompt31", "target": "userinput"},
            {"source": "userinput", "target": "prompt311"},
            {"source": "prompt311", "target": "programme"},
            {"source": "prompt32", "target": "userinput"},
            {"source": "userinput", "target": "prompt321"},
            {"source": "prompt321", "target": "programme"},
        ]
    }

    return jsonify(flow_data)
	

@flow_bp.route('/save_node_data', methods=['POST'])
def save_node_data():
    try:
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid data format"}), 400
        
        node_id = data.get('id')
        node_content = data.get('content')

        if not node_id or node_content is None:
            return jsonify({"error": "Missing node id or content"}), 400

        # 读取现有数据并更新
        node_data_store = read_data()
        node_data_store[node_id] = node_content
        write_data(node_data_store)

        return jsonify({"message": "Node content saved successfully"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to save node content"}), 500
