#!/usr/bin/env python3
"""
查询用户权限组插件
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message
from nonebot.matcher import Matcher
from nonebot import get_driver
from bot import get_db_connection

getrole = on_command(
    "getrole", 
    aliases={}, 
    priority=5, 
    block=True)

@getrole.handle()
async def handle_getrole(event: MessageEvent, matcher: Matcher):
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("请前往群聊使用Bot！(SourXe BotGroup: 1063758858)")
        return
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
    
    user_id = event.user_id
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (str(user_id),))
            
            user_record = cursor.fetchone()
            
            if not user_record:
                # 如果用户不存在，创建新用户记录
                cursor.execute("""
                    INSERT INTO user_info (user_id, role, created_at, last_login) 
                    VALUES (%s, 'user', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (str(user_id),))
                conn.commit()
                user_role = 'user'
            else:
                user_role = user_record['role']
            
            # 权限等级说明
            role_descriptions = {
                'user': '未激活用户',
                'donor': '捐赠者',
                'advanced': '基础用户',
                'admin': '管理员'
            }
            
            description = role_descriptions.get(user_role, '未知权限')
            
            await matcher.send(Message(f"[CQ:at,qq={user_id}] 您的权限组：{description}"))
                
    except Exception as e:
        await matcher.send(f"查询权限组时出错：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "getrole"
__plugin_usage__ = """
查询用户权限组插件

命令列表：
/getrole - 查询当前用户的权限组
"""