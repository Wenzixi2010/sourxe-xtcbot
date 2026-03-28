#!/usr/bin/env python3
"""
基于 NoneBot 框架的 QQ 机器人
"""
import os
import yaml
import pymysql
from pymysql import Error
from dbutils.pooled_db import PooledDB
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

db_pool = None

def load_config():
    try:
        with open('config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        return config
    except Exception as e:
        print(f"加载配置文件失败：{e}")
        return {}

def get_mysql_config():
    config = load_config()
    mysql_config = config.get('mysql_config', {})
    required_fields = ['host', 'port', 'user', 'password', 'database']
    for field in required_fields:
        if field not in mysql_config:
            raise ValueError(f"Config配置文件中缺少MySQL必要的字段: {field}")
    return {
        'host': mysql_config['host'],
        'port': mysql_config['port'],
        'user': mysql_config['user'],
        'password': mysql_config['password'],
        'database': mysql_config['database'],
        'charset': mysql_config.get('charset', 'utf8mb4'),
        'cursorclass': pymysql.cursors.DictCursor
    }

def init_database():
    global db_pool
    try:
        config = get_mysql_config()
        db_pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            mincached=2,
            maxcached=5,
            maxshared=3,
            blocking=True,
            ping=0,
            **config
        )
        print("数据库连接池初始化成功！")
        conn = db_pool.connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_info (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL UNIQUE,
                        role ENUM('user', 'admin', 'donor', 'advanced') DEFAULT 'user',
                        allow_addme BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP NULL,
                        INDEX idx_user_id (user_id),
                        INDEX idx_role (role),
                        INDEX idx_allow_addme (allow_addme)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS devices_info (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        watchid VARCHAR(255),
                        chipid VARCHAR(255),
                        bindnumber VARCHAR(255),
                        model VARCHAR(255),
                        INDEX idx_user_id (user_id),
                        INDEX idx_watchid (watchid),
                        INDEX idx_chipid (chipid),
                        FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE CASCADE
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS likeall_tasks (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        status ENUM('queued', 'processing', 'completed', 'failed') DEFAULT 'queued',
                        message VARCHAR(255),
                        success_count INT DEFAULT 0,
                        total_count INT DEFAULT 0,
                        queue_position INT DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP NULL,
                        completed_at TIMESTAMP NULL,
                        INDEX idx_user_id (user_id),
                        INDEX idx_status (status),
                        FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE CASCADE
                    )
                ''')

                conn.commit()
                print("MySQL数据库表初始化成功！")
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                table_names = [table['Tables_in_xtcsql'] for table in tables] if tables else []
                print(f"当前数据库中的Tables：{table_names}")
                
        finally:
            conn.close()
        
    except Error as e:
        print(f"MySQL数据库初始化失败：{e}")
        db_pool = None

def get_db_connection():
    if db_pool is None:
        raise RuntimeError("数据库连接池未初始化")
    return db_pool.connection()

init_database()
def main(): 
    # 初始化 NoneBot
    os.environ["ENVIRONMENT"] = "dev"
    nonebot.init()
    
    # 注册适配器
    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)
    
    # 加载内置插件
    nonebot.load_builtin_plugins()
    
    # 加载项目插件目录
    nonebot.load_plugins("src/plugins")
    # 启动机器人
    if __name__ == "__main__":
        nonebot.run()

if __name__ == "__main__":
    main()