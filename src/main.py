import schedule
import time
import threading
from datetime import datetime, time as dt_time
from . import config, mail_monitor, webhook


# 调度器状态
scheduler_status = {
    "running": False,
    "enabled": True,
    "in_time_range": False,
    "next_run": None,
    "last_check": None,
    "interval_minutes": 30,
    "start_time": "09:00",
    "end_time": "18:00"
}


def run_schedule():
    """运行定时任务"""
    while True:
        cfg = config.load_config()
        schedule_cfg = cfg.get('schedule', {})
        enabled = schedule_cfg.get('enabled', True)
        start_time = schedule_cfg.get('start_time', '09:00')
        end_time = schedule_cfg.get('end_time', '18:00')
        interval = schedule_cfg.get('interval_minutes', 30)

        # 更新全局状态
        scheduler_status["enabled"] = enabled
        scheduler_status["start_time"] = start_time
        scheduler_status["end_time"] = end_time
        scheduler_status["interval_minutes"] = interval

        if not enabled:
            scheduler_status["running"] = False
            scheduler_status["in_time_range"] = False
            print("定时任务已禁用")
            time.sleep(60)
            continue

        scheduler_status["running"] = True

        # 清除所有定时任务
        schedule.clear()

        # 解析时间
        try:
            start = dt_time(int(start_time.split(':')[0]), int(start_time.split(':')[1]))
            end = dt_time(int(end_time.split(':')[0]), int(end_time.split(':')[1]))
        except:
            start = dt_time(9, 0)
            end = dt_time(18, 0)

        # 设置间隔任务
        schedule.every(interval).minutes.do(run_check)

        print(f"定时任务已设置: {start_time} - {end_time}, 间隔{interval}分钟")

        # 运行主循环
        while True:
            schedule.run_pending()

            # 检查是否在时间范围内
            now = datetime.now().time()
            if now < start or now > end:
                scheduler_status["in_time_range"] = False
                # 不在时间范围内，重新加载配置
                break

            scheduler_status["in_time_range"] = True

            # 计算下次运行时间
            if schedule.jobs:
                next_job = schedule.jobs[0].next_run
                if next_job:
                    scheduler_status["next_run"] = next_job.strftime('%H:%M:%S')

            time.sleep(30)


def run_check():
    """执行邮件检查"""
    cfg = config.load_config()
    schedule_cfg = cfg.get('schedule', {})
    start_time = schedule_cfg.get('start_time', '09:00')
    end_time = schedule_cfg.get('end_time', '18:00')

    # 再次检查是否在时间范围内
    now = datetime.now().time()
    try:
        start = dt_time(int(start_time.split(':')[0]), int(start_time.split(':')[1]))
        end = dt_time(int(end_time.split(':')[0]), int(end_time.split(':')[1]))
    except:
        return  # 时间格式错误，跳过

    if now < start or now > end:
        return  # 不在时间范围内，跳过

    print(f"[{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}] 开始检查邮件...")

    matched_emails, error = mail_monitor.fetch_mails()

    if error:
        print(f"检查邮件失败: {error}")
        config.add_log({
            "id": int(datetime.now().timestamp()),
            "timestamp": datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'),
            "type": "scheduled",
            "matched_emails": 0,
            "webhook_sent": False,
            "details": f"检查失败: {error}"
        })
        return

    if not matched_emails:
        print("没有匹配的邮件")
        config.add_log({
            "id": int(datetime.now().timestamp()),
            "timestamp": datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'),
            "type": "scheduled",
            "matched_emails": 0,
            "webhook_sent": False,
            "details": "没有匹配的邮件"
        })
        return

    print(f"检测到{len(matched_emails)}封匹配邮件")

    # 发送Webhook
    success, message = webhook.send_webhook(matched_emails)

    config.add_log({
        "id": int(datetime.now().timestamp()),
        "timestamp": datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'),
        "type": "scheduled",
        "matched_emails": len(matched_emails),
        "webhook_sent": success,
        "details": message
    })

    print(f"Webhook发送: {message}")


def start_scheduler():
    """启动定时任务线程"""
    thread = threading.Thread(target=run_schedule, daemon=True)
    thread.start()
    return thread


def get_scheduler_status():
    """获取调度器状态"""
    from datetime import datetime
    status = scheduler_status.copy()
    status["current_time"] = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')

    # 计算下次运行时间
    if status["running"] and status["in_time_range"]:
        if schedule.jobs:
            next_job = schedule.jobs[0].next_run
            if next_job:
                status["next_run"] = next_job.strftime('%H:%M:%S')

    return status
