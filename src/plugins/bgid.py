#!/usr/bin/env python3
"""
Bgid插件
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot import get_driver
from bot import get_db_connection

bgid_cmd = on_command(
    "bgid", 
    aliases={}, 
    priority=5, 
    block=True)

# 帮助页面内容
bgid_pages = {
    1: 
"""-----ZxeBot-----
背景id   背景名称
------------------
5        Z8系列
25       大巴车
31       智慧生活
37       星际领航
45       Z9专属动态卡片
57       最佳拍档
59       金
63       雷狮
65       嘉德罗斯
73       丛林探秘
当前页数 1/5""",
    2:
"""-----ZxeBot-----
背景id   背景名称
------------------
75       夏日椰椰
77       ZOO打卡
79       太空考察
81       雪地冒险
87       龙年动态卡片
93       欢乐龙
95       智慧龙
97       勇气龙
99       守护龙
当前页数 2/5""",
    3:
"""-----ZxeBot-----
背景id   背景名称
------------------
105      地球
113      火星
115      月球
155      好友圈动态背景
165      好友圈动态背景
169      网络爬虫
171      蛛丝特工
173      蛛影潜行
175      蜘蛛飞荡
当前页数 3/5""",
    4:
"""-----ZxeBot-----
背景id   背景名称
------------------
185      勤奋蛇
189      智慧蛇
191      友善蛇
193      健康蛇
195      诚信蛇
197      滑冰
199      冬季两项
201      滑雪登山
203      冰球
当前页数 4/5""",
    5:
"""-----ZxeBot-----
背景id   背景名称
------------------
205      冰壶
207      滑雪
209      冬运加油牌
219      Z11
225      哪吒1号
227      哪吒2号
237      敖丙1号
239      敖丙2号
247      Z11少年版
当前页数 5/5"""
}

@bgid_cmd.handle()
async def handle_bgid(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
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

    page_arg = args.extract_plain_text().strip()
    
    try:
        await matcher.send("正在处理您的请求\n提示：Pro服务已开始出售\n捐赠可以使用微聊转发功能，如需购买前往群公告网址")
        if page_arg:
            page_num = int(page_arg)
            if page_num < 1 or page_num > len(bgid_pages):
                await matcher.finish(f"页码无效！请输入 1-{len(bgid_pages)} 之间的数字")
        else:
            page_num = 1
    except ValueError:
        await matcher.finish("指令错误！请输入有效的页码数字")
        return
    await matcher.send(bgid_pages[page_num])

# ==================== 插件元信息 ====================
__plugin_name__ = "bgid"
__plugin_usage__ = """
命令列表：
/bgid - 显示第1页BGID
/bgid [页码] - 显示指定页码
"""
