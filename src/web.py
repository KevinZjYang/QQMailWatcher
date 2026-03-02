from flask import Flask, render_template, jsonify, request, send_from_directory
from datetime import datetime
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src import config, mail_monitor, webhook, main

app = Flask(__name__)


@app.route('/')
def index():
    """主页 - 返回静态HTML文件"""
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'templates'), 'index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取调度器状态"""
    status = main.get_scheduler_status()
    return jsonify(status)


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置"""
    cfg = config.load_config()
    # 返回实际密码（前端可选择显示或隐藏）
    return jsonify(cfg)


@app.route('/api/config', methods=['POST'])
def save_config():
    """保存配置"""
    data = request.get_json()

    # 获取现有配置，保留密码（空字符串或***都保留原有密码）
    existing = config.load_config()
    password = data.get('mail', {}).get('password', '')
    if not password or password == '***':
        data['mail']['password'] = existing.get('mail', {}).get('password', '')

    config.save_config(data)
    return jsonify({'success': True})


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """获取日志"""
    logs = config.load_logs()
    return jsonify(logs)


@app.route('/api/trigger', methods=['POST'])
def trigger_check():
    """手动触发检测"""
    matched_emails, error = mail_monitor.fetch_mails()

    if error:
        config.add_log({
            "id": int(datetime.now().timestamp()),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "type": "manual",
            "matched_emails": 0,
            "webhook_sent": False,
            "details": f"检查失败: {error}"
        })
        return jsonify({'success': False, 'message': error, 'matched_emails': []})

    if not matched_emails:
        config.add_log({
            "id": int(datetime.now().timestamp()),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
def test_regex():
    """测试正则表达式"""
    data = request.get_json()
    pattern = data.get('pattern', '')
    content = data.get('content', '')

    success, result = mail_monitor.test_regex(pattern, content)
    return jsonify({'success': success, 'result': result})


@app.route('/api/test-mail', methods=['POST'])
def test_mail_connection():
    """测试邮箱连接（从配置文件读取）"""
    success, message = mail_monitor.test_connection()
    return jsonify({'success': success, 'message': message})


@app.route('/api/test-webhook', methods=['POST'])
def test_webhook_connection():
    """测试Webhook连接（从配置文件读取）"""
    success, message = webhook.test_webhook()
    return jsonify({'success': success, 'message': message})


@app.route('/api/config/export', methods=['GET'])
def export_config():
    """导出配置"""
    cfg = config.load_config()
    # 导出时保留密码
    return jsonify(cfg)


@app.route('/api/config/import', methods=['POST'])
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
