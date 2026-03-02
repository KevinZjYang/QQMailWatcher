import json
import os

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
LOGS_FILE = os.path.join(CONFIG_DIR, 'logs.json')
PROCESSED_FILE = os.path.join(CONFIG_DIR, 'processed.json')

DEFAULT_CONFIG = {
    "mail": {
        "imap_server": "imap.qq.com",
        "imap_port": 993,
        "username": "",
        "password": ""
    },
    "filter": {
        "subject_startswith": "",
        "sender": "",
        "content_match": {
            "mode": "any",
            "rules": [
                {
                    "id": 1,
                    "pattern": "",
                    "message": "【提醒】收到邮件：{subject}\n发件人：{sender}\n内容：{content}",
                    "enabled": True
                }
            ]
        }
    },
    "schedule": {
        "enabled": True,
        "start_time": "09:00",
        "end_time": "18:00",
        "interval_minutes": 30
    },
    "webhook": {
        "url": ""
    }
}


def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_logs():
    """加载日志"""
    if os.path.exists(LOGS_FILE):
        try:
            with open(LOGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_logs(logs):
    """保存日志"""
    with open(LOGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def add_log(log_entry):
    """添加日志"""
    logs = load_logs()
    logs.insert(0, log_entry)
    # 只保留最近100条日志
    logs = logs[:100]
    save_logs(logs)


def load_processed():
    """加载已处理邮件ID列表"""
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_processed(processed):
    """保存已处理邮件ID列表"""
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)


def add_processed(mail_id):
    """添加已处理邮件ID"""
    processed = load_processed()
    if mail_id not in processed:
        processed.append(mail_id)
        # 只保留最近500个
        processed = processed[-500:]
        save_processed(processed)
