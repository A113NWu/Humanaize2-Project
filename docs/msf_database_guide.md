# MSF数据库接入文档

## 概述

本模块提供了安全、稳定的MSF（Metasploit Framework）数据库接入能力，支持标准的PostgreSQL数据库连接协议，实现了完整的数据读写操作封装，并提供了完善的错误处理机制。

## 目录结构

```
src/core/tools/
├── msf_config.py        # 数据库配置管理模块
├── msf_db.py            # 数据库连接管理器
└── msf_operations.py    # 数据操作封装模块

ai_selfdevelop/skills/msf/
├── SKILL.md             # 技能定义文件
└── __init__.py          # 技能执行模块

config/
└── msf_config.json      # 数据库配置文件（运行时生成）
```

## 配置说明

### 配置文件格式

配置文件位于 `config/msf_config.json`，首次运行时自动生成默认配置：

```json
{
    "host": "127.0.0.1",
    "port": 5432,
    "database": "msf",
    "username": "msf",
    "password": "",
    "ssl_mode": "disable",
    "connect_timeout": 10,
    "pool_size": 5,
    "max_overflow": 10,
    "retry_attempts": 3,
    "retry_delay": 2,
    "query_timeout": 30,
    "encoding": "utf-8"
}
```

### 配置参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| host | string | 127.0.0.1 | 数据库服务器地址 |
| port | int | 5432 | 数据库端口 |
| database | string | msf | 数据库名称 |
| username | string | msf | 用户名 |
| password | string | (空) | 密码 |
| ssl_mode | string | disable | SSL模式（disable/require/verify-full） |
| connect_timeout | int | 10 | 连接超时时间（秒） |
| pool_size | int | 5 | 连接池大小 |
| max_overflow | int | 10 | 连接池最大溢出数 |
| retry_attempts | int | 3 | 重试次数 |
| retry_delay | int | 2 | 重试间隔（秒） |
| query_timeout | int | 30 | 查询超时时间（秒） |
| encoding | string | utf-8 | 字符编码 |

### 配置示例

```python
from src.core.tools.msf_config import msf_config

# 修改配置
msf_config.host = "192.168.1.100"
msf_config.port = 5432
msf_config.database = "msf"
msf_config.username = "msf"
msf_config.password = "your_password_here"
msf_config.ssl_mode = "require"

# 保存配置
msf_config.save_config()

# 验证配置
result = msf_config.validate_config()
print(result)
```

## 接口定义

### 核心模块接口

#### MSFDB类

```python
from src.core.tools.msf_db import msf_db

# 连接数据库
result = msf_db.connect()

# 断开连接
result = msf_db.disconnect()

# 测试连接
result = msf_db.test_connection()

# 获取状态
result = msf_db.get_status()

# 执行查询
result = msf_db.execute_query("SELECT * FROM hosts WHERE state = %s;", ("alive",))

# 执行命令
result = msf_db.execute_command("INSERT INTO hosts (host, state) VALUES (%s, %s);", ("192.168.1.1", "alive"))

# 批量执行
queries = [
    {"query": "INSERT INTO hosts (host) VALUES (%(host)s)", "params": {"host": "192.168.1.1"}},
    {"query": "INSERT INTO hosts (host) VALUES (%(host)s)", "params": {"host": "192.168.1.2"}}
]
result = msf_db.execute_batch(queries)

# 执行事务
result = msf_db.execute_transaction(queries)

# 获取表名列表
result = msf_db.get_table_names()

# 获取表结构
result = msf_db.get_table_columns("hosts")
```

#### MSFOperations类

```python
from src.core.tools.msf_operations import msf_ops

# 获取主机列表
result = msf_ops.get_hosts(filters={"state": "alive", "limit": 10})

# 获取主机详细信息
result = msf_ops.get_host_details(host_id=1)

# 添加主机
result = msf_ops.add_host({
    "host": "192.168.1.1",
    "os_name": "Linux",
    "state": "alive",
    "info": "Ubuntu 22.04",
    "mac": "00:11:22:33:44:55"
})

# 更新主机
result = msf_ops.update_host(host_id=1, host_data={"state": "dead", "info": "Host offline"})

# 删除主机
result = msf_ops.delete_host(host_id=1)

# 获取服务列表
result = msf_ops.get_services(filters={"host_id": 1, "limit": 10})

# 添加服务
result = msf_ops.add_service({
    "host_id": 1,
    "port": 80,
    "proto": "tcp",
    "name": "http",
    "state": "open"
})

# 获取漏洞列表
result = msf_ops.get_vulnerabilities(filters={"severity": "high", "limit": 10})

# 添加漏洞
result = msf_ops.add_vulnerability({
    "host_id": 1,
    "name": "CVE-2024-1234",
    "severity": "high",
    "confidence": 90,
    "description": "Remote code execution vulnerability"
})

# 获取凭据列表
result = msf_ops.get_credentials(filters={"host_id": 1, "limit": 10})

# 添加凭据
result = msf_ops.add_credential({
    "host_id": 1,
    "service": "ssh",
    "username": "admin",
    "password": "password123"
})

# 获取会话列表
result = msf_ops.get_sessions(filters={"is_dead": False, "limit": 10})

# 获取数据库摘要
result = msf_ops.get_summary()

# 执行原始查询
result = msf_ops.execute_raw_query("SELECT COUNT(*) FROM hosts;")

# 执行原始命令
result = msf_ops.execute_raw_command("UPDATE hosts SET state = 'dead' WHERE last_seen < NOW() - INTERVAL '7 days';")
```

### 技能接口

通过技能管理器调用MSF数据库技能：

```python
from src.core.tools.skills_manager import SkillsManager

sm = SkillsManager()

# 连接数据库
result = sm.execute_skill('msf', {'action': 'connect'})

# 获取主机列表
result = sm.execute_skill('msf', {
    'action': 'get_hosts',
    'params': {'filters': {'state': 'alive', 'limit': 10}}
})

# 添加主机
result = sm.execute_skill('msf', {
    'action': 'add_host',
    'params': {'host': '192.168.1.1', 'os_name': 'Linux', 'state': 'alive'}
})

# 获取数据库摘要
result = sm.execute_skill('msf', {'action': 'get_summary'})
```

### AI调用格式

AI通过JSON格式调用MSF技能：

```json
{"skill": "msf", "input": {"action": "get_hosts", "params": {"filters": {"state": "alive", "limit": 10}}}}
```

## 使用示例

### 示例1：连接数据库并获取主机列表

```python
from src.core.tools.msf_db import msf_db
from src.core.tools.msf_operations import msf_ops

# 连接数据库
connect_result = msf_db.connect()
if connect_result["status"] == "success":
    print("Connected successfully")
    
    # 获取主机列表
    hosts = msf_ops.get_hosts(filters={"limit": 5})
    print(f"Found {hosts['count']} hosts")
    
    for host in hosts["data"]:
        print(f"- {host['host']} ({host['os_name']}, {host['state']})")
    
    # 断开连接
    msf_db.disconnect()
else:
    print(f"Connection failed: {connect_result['message']}")
```

### 示例2：批量添加主机

```python
from src.core.tools.msf_db import msf_db
from src.core.tools.msf_operations import msf_ops

msf_db.connect()

hosts_to_add = [
    {"host": "192.168.1.10", "os_name": "Windows", "state": "alive"},
    {"host": "192.168.1.11", "os_name": "Linux", "state": "alive"},
    {"host": "192.168.1.12", "os_name": "Linux", "state": "dead"}
]

for host_data in hosts_to_add:
    result = msf_ops.add_host(host_data)
    if result["status"] == "success":
        print(f"Added host: {host_data['host']}")
    else:
        print(f"Failed to add {host_data['host']}: {result['message']}")

msf_db.disconnect()
```

### 示例3：执行事务操作

```python
from src.core.tools.msf_db import msf_db

msf_db.connect()

# 执行事务
queries = [
    {"query": "INSERT INTO hosts (host, state) VALUES (%(host1)s, 'alive')", "params": {"host1": "192.168.1.20"}},
    {"query": "INSERT INTO services (host_id, port, proto) VALUES ((SELECT id FROM hosts WHERE host = %(host)s), 80, 'tcp')", "params": {"host": "192.168.1.20"}}
]

result = msf_db.execute_transaction(queries)
if result["status"] == "success":
    print("Transaction completed successfully")
else:
    print(f"Transaction failed: {result['message']}")

msf_db.disconnect()
```

## 错误处理

### 错误返回格式

所有操作返回统一的错误格式：

```json
{
    "status": "error",
    "message": "Error description"
}
```

### 常见错误类型

| 错误类型 | 说明 |
|----------|------|
| Not connected to database | 未连接数据库 |
| Database error | 数据库操作错误 |
| Missing required field | 缺少必填字段 |
| Host not found | 主机不存在 |
| Failed to initialize connection pool | 连接池初始化失败 |
| Failed to get database connection after retries | 获取连接失败 |

### 异常处理示例

```python
from src.core.tools.msf_db import msf_db, MSFDBError

try:
    result = msf_db.connect()
    
    if result["status"] == "success":
        hosts = msf_db.execute_query("SELECT * FROM hosts;")
        
        if hosts["status"] == "success":
            print(f"Total hosts: {hosts['count']}")
        else:
            print(f"Query error: {hosts['message']}")
            
        msf_db.disconnect()
    else:
        print(f"Connection error: {result['message']}")
        
except MSFDBError as e:
    print(f"MSF DB Error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## 安全性考虑

### 1. 密码保护

- 配置文件中的密码使用明文存储，建议在生产环境中使用环境变量或密钥管理服务
- 在日志输出中自动隐藏密码信息

### 2. SSL连接

- 支持SSL连接模式（require/verify-full）
- 建议在远程连接时启用SSL

### 3. 参数化查询

- 所有数据库操作使用参数化查询，防止SQL注入攻击
- 禁止直接拼接SQL字符串

### 4. 连接池管理

- 使用连接池限制并发连接数
- 自动清理过期连接

### 5. 错误日志

- 详细记录数据库操作日志
- 敏感信息（如密码）不记录到日志中

## 与现有系统集成

### 在Solve模式中使用

通过技能调用方式在Solve模式中使用MSF数据库：

```json
{"skill": "msf", "input": {"action": "get_summary"}}
```

### 在Chat模式中使用

AI可以直接调用MSF技能查询数据库信息：

```
用户：查询MSF数据库中的主机数量
AI：{"skill": "msf", "input": {"action": "get_summary"}}
```

### 自定义扩展

可以通过继承MSFOperations类添加自定义操作：

```python
from src.core.tools.msf_operations import MSFOperations

class CustomMSFOperations(MSFOperations):
    def get_alive_host_count(self):
        """获取存活主机数量"""
        query = "SELECT COUNT(*) FROM hosts WHERE state = 'alive';"
        result = self.execute_raw_query(query)
        return result.get("data", [{"count": 0}])[0].get("count", 0)
```

## 依赖安装

```bash
# 安装psycopg2
pip install psycopg2-binary

# 或使用源码安装
pip install psycopg2
```

## 注意事项

1. MSF数据库通常使用PostgreSQL，请确保已安装并配置好PostgreSQL服务
2. 默认数据库配置为MSF标准配置（msf/msf），请根据实际情况修改
3. 连接数据库需要相应的权限，请确保用户名和密码正确
4. 在Linux系统中，建议使用systemd管理数据库服务
5. 定期备份数据库以防止数据丢失

## 故障排除

### 连接失败

1. 检查数据库服务器是否运行
2. 检查网络连接是否正常
3. 验证用户名和密码是否正确
4. 检查防火墙规则是否允许访问

### 查询超时

1. 检查网络延迟
2. 优化查询语句
3. 增加query_timeout配置

### 权限错误

1. 检查数据库用户权限
2. 验证表和字段的访问权限

### SSL连接错误

1. 检查SSL证书配置
2. 确认SSL模式设置正确
3. 验证证书有效性