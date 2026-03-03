from flask import Flask, render_template, jsonify, request, send_from_directory
from datetime import datetime
from functools import wraps
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src import config, mail_monitor, webhook, main

app = Flask(__name__)


def require_auth(f):
    """认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        password = request.headers.get('X-Admin-Password', '')
        cfg = config.load_config()
        admin_cfg = cfg.get('admin', {})
        stored_password = admin_cfg.get('password', 'admin123')

        # 如果密码为空，则不启用认证
        if not stored_password:
            return f(*args, **kwargs)

        if password != stored_password:
            return jsonify({'success': False, 'message': '未授权'}), 401
        return f(*args, **kwargs)
    return decorated_function


# 启动定时任务（在 gunicorn 模式下也会启动）
main.start_scheduler()


@app.route('/')
def index():
    """主页 - 返回静态HTML文件"""
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'templates'), 'index.html')


@app.route('/api/login', methods=['POST'])
def login():
    """登录验证"""
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')

    cfg = config.load_config()
    admin_cfg = cfg.get('admin', {})

    stored_username = admin_cfg.get('username', 'admin')
    stored_password = admin_cfg.get('password', 'admin123')

    # 如果密码为空，则不启用认证
    if not stored_password:
        return jsonify({'success': True, 'message': '登录成功'})

    if username == stored_username and password == stored_password:
        return jsonify({'success': True, 'message': '登录成功'})
    return jsonify({'success': False, 'message': '用户名或密码错误'}), 401


@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """检查认证状态"""
    password = request.headers.get('X-Admin-Password', '')
    cfg = config.load_config()
    admin_cfg = cfg.get('admin', {})
    stored_password = admin_cfg.get('password', 'admin123')

    if not stored_password:
        return jsonify({'success': True, 'authenticated': True})

    if password == stored_password:
        return jsonify({'success': True, 'authenticated': True})
    return jsonify({'success': True, 'authenticated': False})


@app.route('/api/status', methods=['GET'])
@require_auth
def get_status():
    """获取调度器状态"""
    status = main.get_scheduler_status()
    return jsonify(status)


@app.route('/api/config', methods=['GET'])
@require_auth
def get_config():
    """获取配置"""
    cfg = config.load_config()
    # 返回实际密码（前端可选择显示或隐藏）
    return jsonify(cfg)


@app.route('/api/config', methods=['POST'])
@require_auth
def save_config():
    """保存配置"""
    data = request.get_json()

    print(f"[DEBUG] save_config received: {data}")

    # 获取现有配置，保留密码（空字符串或***都保留原有密码）
    existing = config.load_config()
    password = data.get('mail', {}).get('password', '')
    if not password or password == '***':
        data['mail']['password'] = existing.get('mail', {}).get('password', '')

    # 保留现有 admin 配置（如果没有传 admin 字段或字段不完整）
    if 'admin' not in data:
        data['admin'] = existing.get('admin', {})
        print(f"[DEBUG] No admin in data, using existing: {data['admin']}")
    else:
        admin_data = data.get('admin', {})
        existing_admin = existing.get('admin', {})

        print(f"[DEBUG] admin_data from frontend: {admin_data}")
        print(f"[DEBUG] existing_admin: {existing_admin}")

        # 如果传了 admin 且有 password 且不为空，使用新密码
        # 否则保留旧密码
        if admin_data.get('password'):
            # 使用前端传来的新密码
            print(f"[DEBUG] Using new password: {admin_data['password']}")
        else:
            admin_data['password'] = existing_admin.get('password', 'admin123')
            print(f"[DEBUG] Keeping old password: {admin_data['password']}")

        # 如果传了 admin 且有 username 且不为空，使用新用户名
        # 否则保留旧用户名
        if admin_data.get('username'):
            pass  # 使用前端传来的新用户名
        else:
            admin_data['username'] = existing_admin.get('username', 'admin')

        data['admin'] = admin_data
        print(f"[DEBUG] Final admin data to save: {data['admin']}")

    config.save_config(data)
    print(f"[DEBUG] Saved config successfully")
    return jsonify({'success': True})


@app.route('/api/logs', methods=['GET'])
@require_auth
def get_logs():
    """获取日志"""
    logs = config.load_logs()
    return jsonify(logs)


@app.route('/api/emails', methods=['GET'])
@require_auth
def get_emails():
    """获取邮件列表"""
    matched_filter = request.args.get('matched')

    # 获取已保存的邮件列表
    emails = config.load_emails()

    # 过滤
    if matched_filter == 'true':
        emails = [e for e in emails if e.get('matched', False)]
    elif matched_filter == 'false':
        emails = [e for e in emails if not e.get('matched', False)]

    # 简化返回数据（不返回 full_content 减少传输量）
    for email in emails:
        if 'full_content' in email:
            del email['full_content']

    return jsonify({'success': True, 'emails': emails})


@app.route('/api/trigger', methods=['POST'])
@require_auth
def trigger_check():
    """手动触发检测"""
    # 先获取所有邮件（用于排查）
    all_emails, error = mail_monitor.fetch_mails(return_all=True)

    # 再获取匹配的邮件用于发送webhook
    matched_emails, error = mail_monitor.fetch_mails()

    if error:
        config.add_log({
            "id": int(datetime.now().timestamp()),
            "timestamp": datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'),
            "type": "manual",
            "matched_emails": 0,
            "webhook_sent": False,
            "details": f"检查失败: {error}"
        })
        return jsonify({'success': False, 'message': error, 'matched_emails': []})

    if not matched_emails:
        config.add_log({
            "id": int(datetime.now().timestamp()),
            "timestamp": datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'),
            "type": "manual",
            "matched_emails": 0,
            "webhook_sent": False,
            "details": "没有匹配的邮件"
        })
        return jsonify({'success': True, 'message': '没有匹配的邮件', 'matched_emails': []})

    # 发送Webhook
    success, message = webhook.send_webhook(matched_emails)

    # 格式化匹配的邮件信息
    emails_info = []
    for email_data in matched_emails:
        rule = email_data.get('matched_rule', {})
        emails_info.append({
            'subject': email_data.get('subject', ''),
            'sender': email_data.get('sender', ''),
            'content': email_data.get('content', '')[:200],
            'rule': rule.get('pattern', ''),
            'message': rule.get('message', '')[:100]
        })

    config.add_log({
        "id": int(datetime.now().timestamp()),
        "timestamp": datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'),
        "type": "manual",
        "matched_emails": len(matched_emails),
        "webhook_sent": success,
        "details": message
    })

    return jsonify({
        'success': success,
        'message': message,
        'matched_emails': emails_info
    })


@app.route('/api/test-regex', methods=['POST'])
@require_auth
def test_regex():
    """测试正则表达式"""
    data = request.get_json()
    pattern = data.get('pattern', '')
    content = data.get('content', '')

    success, result = mail_monitor.test_regex(pattern, content)
    return jsonify({'success': success, 'result': result})


@app.route('/api/test-mail', methods=['POST'])
@require_auth
def test_mail_connection():
    """测试邮箱连接（从配置文件读取）"""
    success, message = mail_monitor.test_connection()
    return jsonify({'success': success, 'message': message})


@app.route('/api/test-webhook', methods=['POST'])
@require_auth
def test_webhook_connection():
    """测试Webhook连接（从配置文件读取）"""
    success, message = webhook.test_webhook()
    return jsonify({'success': success, 'message': message})


@app.route('/api/config/export', methods=['GET'])
@require_auth
def export_config():
    """导出配置"""
    cfg = config.load_config()
    # 导出时保留密码
    return jsonify(cfg)


@app.route('/api/config/import', methods=['POST'])
@require_auth
def import_config():
    """导入配置"""
    try:
        data = request.get_json()
        # 验证必要字段
        if 'mail' not in data or 'filter' not in data or 'schedule' not in data or 'webhook' not in data:
            return jsonify({'success': False, 'message': '配置文件格式不正确'})

        # 获取现有配置，保留密码（空字符串或***都保留原有密码）
        existing = config.load_config()
        password = data.get('mail', {}).get('password', '')
        if not password or password == '***':
            data['mail']['password'] = existing.get('mail', {}).get('password', '')

        config.save_config(data)
        return jsonify({'success': True, 'message': '配置导入成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'导入失败: {str(e)}'})


if __name__ == '__main__':
    # 启动定时任务
    main.start_scheduler()
    # 启动Web服务器
    app.run(host='0.0.0.0', port=3020, debug=False)
