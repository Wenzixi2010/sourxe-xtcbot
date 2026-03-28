\# NoneBot2 Sourxe-XTCBot

\*\*声明\*\*：本项目使用了 \*\*VibeCoding\*\* 进行辅助开发。



基于 NoneBot2 框架开发，接入 Napcat 的 QQ 机器人项目。本项目使用 MySQL 进行数据存储，并集成了相关手表 API 接口，实现了多维度的设备与用户数据管理功能。



\## 环境要求



\* \*\*Python\*\*: 3.9+

\* \*\*MySQL\*\*: <= 8.4.6

\* \*\*OneBot 客户端\*\*: \[Napcat](https://github.com/NapNeko/NapCatQQ)



\## 安装与配置



\### 1. 安装依赖

首先，将本项目克隆到本地。请确保你的环境中已安装 Python 3.9+。

然后在项目根目录下运行以下命令安装所需依赖：

```bash

pip3 install -r requirements.txt

```

\### 2. 修改配置文件

\- 配置 .env 文件

&#x20; - 复制项目中的 .env.example 文件并重命名为 .env.dev 根据你的实际配置和需求进行修改：

\- 配置 ENVIRONMENT=dev 与 DRIVER=\~fastapi 。

&#x20; - 配置Napcat 客户端连接所需的 HOST=0.0.0.0、PORT 和 SECRET

&#x20; - UPERUSERS=\["your-admin-qqid"] 中填入管理员QQ号

&#x20; - ALLOWED\_GROUPS 中填入白名单群号如 \["000000001"]



\- 配置 config.yaml 文件

&#x20; - 配置 mysql\_config 节点下的 host、port、user、password 和 database 字段

\### 3. 运行

\- 配置好数据库连接信息后，第一次使用先初始化数据库表

```bash

python3 init\_database.py

```

\- 启动

```bash

python3 bot.py

```

