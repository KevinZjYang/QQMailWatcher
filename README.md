# QQMailWatcher

监控QQ邮箱的特定邮件，通过企业微信Webhook发送通知。

## 功能特性

- IMAP邮件监控
- 支持按邮件主题、发件人过滤
- 支持正则表达式内容匹配，多规则自定义消息
- 定时任务（时间段 + 间隔）
- Web管理界面
- 配置导入导出
- Docker部署支持

## 快速开始

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python src/web.py
```

访问 http://127.0.0.1:3020

### Docker部署

```bash
# 构建并启动
docker-compose up -d
```

访问 http://localhost:3020

## 配置说明

### 邮箱设置

- IMAP服务器：`imap.qq.com`
- IMAP端口：`993`
- 用户名：你的QQ邮箱
- 授权码：在QQ邮箱设置中生成

### 过滤规则

- **邮件主题开头**：只监控主题以指定文字开头的邮件
- **发件人**：只监控指定发件人的邮件

### 内容匹配规则

支持正则表达式匹配邮件内容，可配置多条规则：

- **任一匹配**：邮件内容匹配任一规则即可触发
- **全部符合**：邮件内容需匹配所有规则才触发

每条规则可单独设置：
- 正则表达式
- 消息模板
- 启用/禁用

消息模板变量：
- `{subject}` - 邮件主题
- `{sender}` - 发件人
- `{content}` - 邮件正文摘要
- `{date}` - 邮件日期
- `{full_content}` - 完整正文

### 定时任务

- 启用/禁用开关
- 开始时间、结束时间（只在时间段内检测）
- 检测间隔（10/15/30/60分钟）

### Webhook

企业微信机器人Webhook URL，格式：
```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

## 项目结构

```
QQMailWatcher/
├── data/
│   ├── config.json      # 配置文件
│   ├── logs.json        # 运行日志
│   └── processed.json   # 已处理邮件
├── src/
│   ├── config.py        # 配置管理
│   ├── mail_monitor.py  # 邮件监控
│   ├── webhook.py       # Webhook发送
│   ├── main.py         # 定时任务
│   ├── web.py          # Web服务
│   └── templates/
│       └── index.html  # 管理界面
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 注意事项

1. QQ邮箱需开启IMAP并生成授权码
2. 定时任务只在设定的时间段内执行检测
3. 已处理的邮件不会重复发送通知
4. 建议检测间隔设置为15-30分钟，避免频繁登录
