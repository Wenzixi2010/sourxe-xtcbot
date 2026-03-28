#!/usr/bin/env python3
"""
解绑设备插件
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.matcher import Matcher
from nonebot import get_driver
from bot import get_db_connection

unbind = on_command(
    "unbind", 
    aliases={}, 
    priority=5, 
    block=True)

@unbind.handle()
async def handle_unbind(event: MessageEvent, matcher: Matcher):
    driver = get_driver()
    allowed_groups = driver.config.allowed_groups
    if str(event.group_id) not in allowed_groups:
        return
    
    user_id = event.user_id
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT d.watchid, d.model 
                FROM devices_info d
                WHERE d.user_id = %s
            """, (user_id,))
            
            device_record = cursor.fetchone()
            
            if not device_record:
                await matcher.send("您还没有绑定设备，无需解绑")
                return
                
    except Exception as e:
        await matcher.send(f"命令执行失败 {e}")
        return
    finally:
        if 'conn' in locals():
            conn.close()
    
    at_message = MessageSegment.at(user_id) + " 您确定要解绑设备吗？\n"
    at_message += f"设备信息：\n"
    at_message += f"- WatchID：{device_record['watchid']}\n"
    at_message += f"- 设备型号：{device_record['model']}\n\n"
    at_message += "请回复：\n"
    at_message += "是 - 确认执行操作\n"
    at_message += "否 - 取消执行操作"
    
    await matcher.send(at_message)
    
    matcher.set_arg("confirm_unbind", Message("等待确认"))

@unbind.got("confirm_unbind")
async def got_confirmation(event: MessageEvent, matcher: Matcher):
    driver = get_driver()
    allowed_groups = driver.config.allowed_groups
    if str(event.group_id) not in allowed_groups:
        return
    user_id = event.user_id
    confirmation = str(event.get_message()).strip().lower()
    
    if confirmation in ["是", "yes", "y", "确认", "确定"]:
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM devices_info 
                    WHERE user_id = %s
                """, (user_id,))
                
                conn.commit()
                
                success_msg = MessageSegment.at(user_id) + " 设备解绑成功！\n"
                success_msg += "已删除您的设备信息"
                await matcher.send(success_msg)
                
        except Exception as e:
            print(f"解绑操作失败：{e}")
            error_msg = MessageSegment.at(user_id) + " 解绑失败，请稍后重试。"
            await matcher.send(error_msg)
        finally:
            if 'conn' in locals():
                conn.close()
                
    elif confirmation in ["否", "no", "n", "取消"]:
        cancel_msg = MessageSegment.at(user_id) + " 已取消解绑操作。"
        await matcher.send(cancel_msg)
    else:
        reject_msg = MessageSegment.at(user_id) + " 请输入有效的确认选项：\n"
        reject_msg += "是 - 执行操作\n"
        reject_msg += "否 - 取消执行操作"
        await matcher.reject(reject_msg)

__plugin_name__ = "unbind"
__plugin_usage__ = """
解绑设备插件
"""