import imaplib
import email
import re
import json
from email.header import decode_header
from datetime import datetime
from . import config


def decode_email_header(header):
    """解码邮件头部"""
    if not header:
        return ""
    decoded = decode_header(header)
    result = ""
    for part, encoding in decoded:
        if isinstance(part, bytes):
            part = part.decode(encoding or 'utf-8', errors='ignore')
        result += part
    return result


def get_email_body(msg):
    """获取邮件正文"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == 'text/plain':
                try:
                    body = part.get_payload(decode=True).decode(
                        part.get_content_charset() or 'utf-8', errors='ignore'
                    )
                    break
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode(
                msg.get_content_charset() or 'utf-8', errors='ignore'
            )
        except:
            body = str(msg.get_payload())
    return body


def check_email_match(mail_config, filter_config, email_data):
    """检查邮件是否匹配过滤规则"""
    subject = email_data.get('subject', '')
    sender = email_data.get('sender', '')
    content = email_data.get('content', '')

    # 主题过滤（非必填）
    subject_startswith = filter_config.get('subject_startswith', '').strip()
    if subject_startswith and not subject.startswith(subject_startswith):
        return None, []

    # 发件人过滤（非必填）
    sender_filter = filter_config.get('sender', '').strip()
    if sender_filter and sender != sender_filter:
        return None, []

    # 内容匹配
    content_match = filter_config.get('content_match', {})
    rules = content_match.get('rules', [])
    mode = content_match.get('mode', 'any')

    matched_rules = []
    for rule in rules:
        if not rule.get('enabled', True):
            continue
        pattern = rule.get('pattern', '').strip()
        if not pattern:
            continue

        try:
            if re.search(pattern, content, re.IGNORECASE):
                matched_rules.append(rule)
        except re.error:
            continue

    if not rules or not any(r.get('enabled') for r in rules):
        # 如果没有配置内容规则，则匹配所有
        return email_data, []

    if mode == 'any':
        # 任一匹配
        return (email_data, matched_rules) if matched_rules else (None, [])
    else:
        # 全部符合 - 检查是否所有启用的规则都匹配
        enabled_rules = [r for r in rules if r.get('enabled', True)]
        if enabled_rules and len(matched_rules) == len(enabled_rules):
            return email_data, matched_rules
        return None, []


def fetch_mails(return_all=False):
    """获取匹配的邮件

    Args:
        return_all: 如果为True，返回所有邮件（包括未匹配的）

    Returns:
        (matched_emails, error) - 匹配的邮件列表和错误信息
    """
    cfg = config.load_config()
    mail_cfg = cfg.get('mail', {})
    filter_cfg = cfg.get('filter', {})

    username = mail_cfg.get('username', '')
    password = mail_cfg.get('password', '')
    imap_server = mail_cfg.get('imap_server', 'imap.qq.com')
    imap_port = mail_cfg.get('imap_port', 993)
    mail_limit = mail_cfg.get('mail_limit', 50)

    if not username or not password:
        return [], "邮箱未配置"

    try:
        # 连接QQ邮箱IMAP
        mail = imaplib.IMAP4_SSL(host=imap_server, port=imap_port)
        mail.login(username, password)
        mail.select('INBOX')

        # 获取定时任务配置
        schedule_cfg = cfg.get('schedule', {})
        schedule_enabled = schedule_cfg.get('enabled', True)
        start_time = schedule_cfg.get('start_time', '09:00')
        end_time = schedule_cfg.get('end_time', '18:00')

        # 解析时间
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))

        from datetime import datetime, timedelta
        # 获取今天的日期
        today = datetime.now().strftime('%d-%b-%Y')

        # 搜索今天的邮件
        status, messages = mail.search(None, f'SINCE {today}')
        if status != 'OK':
            mail.logout()
            return [], "搜索邮件失败"

        mail_ids = messages[0].split()
        # 只处理最近的N封邮件
        mail_ids = mail_ids[-mail_limit:] if len(mail_ids) > mail_limit else mail_ids

        matched_emails = []
        all_emails = []  # 所有获取到的邮件
        processed_ids = config.load_processed()

        for mail_id in reversed(mail_ids):
            if mail_id.decode() in processed_ids and not return_all:
                continue

            status, msg_data = mail.fetch(mail_id, '(RFC822)')
            if status != 'OK':
                continue

            msg = email.message_from_bytes(msg_data[0][1])

            # 提取邮件信息
            subject = decode_email_header(msg.get('Subject', ''))
            sender = decode_email_header(msg.get('From', ''))
            date_header = msg.get('Date', '')
            content = get_email_body(msg)

            # 解析邮件时间并检查是否在时间段内
            # return_all=True 时跳过时间段过滤（用于排查）
            if schedule_enabled and not return_all:
                try:
                    from email.utils import parsedate_to_datetime
                    email_time = parsedate_to_datetime(date_header)
                    email_hour = email_time.hour
                    email_minute = email_time.minute
                    email_time_minutes = email_hour * 60 + email_minute
                    start_time_minutes = start_hour * 60 + start_min
                    end_time_minutes = end_hour * 60 + end_min

                    # 检查是否在时间段内
                    if not (start_time_minutes <= email_time_minutes <= end_time_minutes):
                        if not return_all:
                            continue
                except:
                    pass  # 如果解析失败，跳过时间过滤

            # 提取发件人邮箱地址
            sender_match = re.search(r'<(.+?)>', sender)
            if sender_match:
                sender = sender_match.group(1)

            date = date_header

            email_data = {
                'id': mail_id.decode(),
                'subject': subject,
                'sender': sender,
                'date': date,
                'content': content[:500],  # 截取前500字符
                'full_content': content
            }

            matched_email, matched_rules = check_email_match(mail_cfg, filter_cfg, email_data)

            if matched_email and matched_rules:
                for rule in matched_rules:
                    email_data['matched_rule'] = rule
                    matched_emails.append(email_data.copy())
                # 标记为已处理
                config.add_processed(mail_id.decode())

            # 记录所有邮件（用于排查）
            if return_all:
                email_data['matched'] = bool(matched_email and matched_rules)
                email_data['matched_rule'] = matched_rules[0] if matched_rules else None
                all_emails.append(email_data)

        mail.logout()

        if return_all:
            # 保存所有邮件到列表
            config.add_emails(all_emails)
            return all_emails, None

        return matched_emails, None

    except Exception as e:
        return [], str(e)


def test_connection():
    """测试邮箱连接（从配置文件读取）"""
    cfg = config.load_config()
    mail_cfg = cfg.get('mail', {})
    return test_connection_with_config(mail_cfg)


def test_connection_with_config(mail_cfg):
    """测试邮箱连接（直接传入配置）"""
    username = mail_cfg.get('username', '')
    password = mail_cfg.get('password', '')
    imap_server = mail_cfg.get('imap_server', 'imap.qq.com')
    imap_port = mail_cfg.get('imap_port', 993)

    if not username or not password:
        return False, "邮箱未配置"

    try:
        mail = imaplib.IMAP4_SSL(host=imap_server, port=imap_port)
        mail.login(username, password)
        mail.logout()
        return True, "连接成功"
    except Exception as e:
        return False, str(e)


def test_regex(pattern, content):
    """测试正则表达式"""
    try:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return True, match.group(0)
        return False, "无匹配"
    except re.error as e:
        return False, f"正则表达式错误: {e}"
