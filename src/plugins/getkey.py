#!/usr/bin/env python3

import random
from datetime import datetime, timedelta
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, PrivateMessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from bot import get_db_connection

getkey = on_command(
    "getkey", 
    aliases={"获取密钥"}, 
    priority=5, 
    block=True)

@getkey.handle()
async def handle_getkey(event: MessageEvent, matcher: Matcher):
    if not isinstance(event, PrivateMessageEvent):
        await matcher.finish("请在私聊中使用此命令！")
        return
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return

    try:
        user_id = event.user_id
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (str(user_id),))
            user_record = cursor.fetchone()
            
            # 允许的权限：admin、donor、advanced
            allowed_roles = ['admin', 'donor', 'advanced']
            if not user_record or user_record['role'] not in allowed_roles:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 权限不足！请前往https://shop.sourxe.team购买Zxebot基础版激活码[5r]并使用/ac 激活码 激活后使用(不然我要亏死了)"))
                return
                
    except Exception as e:
        await matcher.send(Message(f"[CQ:at,qq={user_id}] 权限检查过程中出错：{str(e)}"))
        return
    finally:
        if 'conn' in locals():
            conn.close()

    user_id = event.user_id
    
    # 生成6位随机数字密钥
    token = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_info (user_id, role, created_at, last_login) 
                VALUES (%s, 'user', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
                ON DUPLICATE KEY UPDATE last_login = CURRENT_TIMESTAMP
            """, (user_id,))
            cursor.execute("""
                SELECT d.chipid, d.bindnumber, d.watchid, d.model
                FROM devices_info d
                WHERE d.user_id = %s
            """, (user_id,))
            
            conn.commit()

            device_record = cursor.fetchone()
            
            if not device_record:
                await matcher.send("您还没有绑定设备，请先使用 /bindwatch 命令绑定设备（直接发送后面不用跟参数）")
                return
        with conn.cursor() as cursor:
            # 创建临时令牌表（如果不存在）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS moment_temp_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    token VARCHAR(6) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_token (token),
                    INDEX idx_expires_at (expires_at)
                )
            ''')
            
            # 删除该用户之前的所有令牌
            cursor.execute("DELETE FROM moment_temp_tokens WHERE user_id = %s", (user_id,))
            
            # 设置10分钟后过期
            expires_at = datetime.now() + timedelta(minutes=10)
            cursor.execute(
                "INSERT INTO moment_temp_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)",
                (user_id, token, expires_at)
            )
            
            conn.commit()
            
        await matcher.send(f"您的临时登录密钥是：{token}\n请在10分钟内使用此密钥在网页版好友圈登录。\n访问 http://bot.sourxe.team/moments 登录")
        
    except Exception as e:
        await matcher.send(f"生成临时密钥失败：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "getkey"
__plugin_usage__ = """
获取好友圈临时密钥插件

命令列表：
/getkey - 生成用于网页版好友圈登录的临时密钥（6位数字组合）
"""
