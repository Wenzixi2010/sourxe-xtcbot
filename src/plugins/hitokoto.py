#!/usr/bin/env python3
"""
一言动态插件 - 获取一言并发送到好友圈
"""

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from modules import Apirequests
from bot import get_db_connection
import aiohttp

hitokoto = on_command(
    "hitokoto", 
    aliases={}, 
    priority=10, 
    block=True
)

@hitokoto.handle()
async def handle_hitokoto(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("请前往群聊使用Bot！(SourXe BotGroup: 1063758858)")
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

    content = args.extract_plain_text().strip()
    bgid = 105
    if content:
        parts = content.split()
        if parts[-1].isdigit():
            bgid = int(parts[-1])
            if len(parts) > 1:
                content = ' '.join(parts[:-1])
            else:
                content = ""
    
    user_id = event.user_id
    try:
        await matcher.send("正在处理您的请求\n提示：Pro服务已开始出售\n捐赠可以使用微聊转发功能，如需购买前往群公告网址")
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
            
            chipid = device_record['chipid']
            bindnumber = device_record['bindnumber']
            watchid = device_record['watchid']
            model = device_record['model']
            
            # 获取一言
            hitokoto_text = await get_hitokoto(content)
            if not hitokoto_text:
                await matcher.send("获取一言失败，请稍后重试")
                return
            
            # 发送到动态
            response = Apirequests.moment(watchid, bindnumber, chipid, model, hitokoto_text, bgid)
            if response['code'] == '000001':
                await matcher.send(f"一言动态发送成功！\n"
                                    f"----------------------\n"
                                    f"返回码：{response['code']}\n"
                                    f"Info：{response['desc']}\n"
                                    f"背景ID：{bgid}\n"
                                    f"----------------------\n"
                                    f"一言内容：\n{hitokoto_text}"
                                    )
            else:
                await matcher.send(f"一言动态发送失败！\n"
                                    f"----------------------\n"
                                    f"返回码：{response['code']}\n"
                                    f"Info：{response['desc']}")
            
    except Exception as e:
        print(f"操作失败：{e}")
        await matcher.send("操作失败，请稍后重试")
    finally:
        if 'conn' in locals():
            conn.close()

async def get_hitokoto(types=""):
    """
    获取一言
    types: 一言类型，可选参数
    """
    try:
        url = "https://v1.hitokoto.cn/"
        params = {}
        if types:
            params["c"] = types
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    hitokoto = data.get("hitokoto", "")
                    from_who = data.get("from_who", "")
                    from_work = data.get("from", "")
                    
                    result = hitokoto
                    if from_who:
                        result += f" —— {from_who}"
                    if from_work:
                        result += f"《{from_work}》"
                    
                    return result
                else:
                    return None
    except Exception as e:
        print(f"获取一言失败：{e}")
        return None

__plugin_name__ = "hitokoto"
__plugin_usage__ = """
一言动态插件

命令列表：
/hitokoto - 获取一言并发送到动态（默认背景ID 105）
/hitokoto 200 - 获取一言并使用背景ID 200发送
/hitokoto a 200 - 获取动画类型一言并使用背景ID 200发送

一言类型参数（可选）：
a - 动画
b - 漫画
c - 游戏
d - 文学
e - 原创
f - 网络
g - 其他
h - 影视
i - 诗词
j - 网易云
k - 哲学
l - 抖机灵
"""