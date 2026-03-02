import requests
import re
from datetime import datetime
from . import config


def render_message(template, email_data):
    """渲染消息模板"""
    content = email_data.get('content', '')[:200]  # 摘要前200字
    full_content = email_data.get('full_content', '')

    # 清理内容中的多余空白
    content = re.sub(r'\s+', ' ', content)
    full_content = re.sub(r'\s+', ' ', full_content)

    variables = {
        'subject': email_data.get('subject', ''),
        'sender': email_data.get('sender', ''),
        'content': content,
        'date': email_data.get('date', ''),
        'full_content': full_content
    }

    message = template
    for key, value in variables.items():
        message = message.replace(f'{{{key}}}', str(value))

    return message


def send_webhook(matched_emails):
    """发送Webhook消息"""
    cfg = config.load_config()
    webhook_url = cfg.get('webhook', {}).get('url', '')

    if not webhook_url:
        return False, "Webhook URL未配置"

    if not matched_emails:
        return False, "没有匹配的邮件"

    success_count = 0
    errors = []

    for email_data in matched_emails:
        rule = email_data.get('matched_rule', {})
        template = rule.get('message', '【提醒】收到邮件：{subject}\n发件人：{sender}\n内容：{content}')

        message = render_message(template, email_data)

        try:
            response = requests.post(
                webhook_url,
                json={'msgtype': 'text', 'text': {'content': message}},
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    success_count += 1
                else:
                    errors.append(f"企业微信API错误: {result.get('errmsg', '未知错误')}")
            else:
                errors.append(f"HTTP错误: {response.status_code}")

        except requests.exceptions.RequestException as e:
            errors.append(f"请求异常: {str(e)}")

    if success_count > 0:
        return True, f"成功发送{success_count}条消息"
    return False, "; ".join(errors) if errors else "发送失败"


def test_webhook():
    """测试Webhook连接（从配置文件读取）"""
    cfg = config.load_config()
    webhook_cfg = cfg.get('webhook', {})
    return test_webhook_with_config(webhook_cfg)


def test_webhook_with_config(webhook_cfg):
    """测试Webhook连接（直接传入配置）"""
    webhook_url = webhook_cfg.get('url', '')

    if not webhook_url:
        return False, "Webhook URL未配置"

    test_message = "【测试】QQ邮箱监控Webhook测试消息"

    try:
        response = requests.post(
            webhook_url,
            json={'msgtype': 'text', 'text': {'content': test_message}},
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                return True, "发送成功"
            return False, f"企业微信API错误: {result.get('errmsg', '未知错误')}"
        return False, f"HTTP错误: {response.status_code}"

    except requests.exceptions.RequestException as e:
        return False, f"请求异常: {str(e)}"
