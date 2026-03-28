#!/usr/bin/env python3
"""
帮助插件
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot import get_driver

help_cmd = on_command(
    "help", 
    aliases={}, 
    priority=5, 
    block=True)

# 帮助页面内容
help_pages = {
    1: 
"""-----ZxeBot-----
 /getrole 查询权限组
 /bindhelp 绑定教程
 /activate 激活Pro
 /bindwatch 绑定手表（直接发送后面不用跟参数）
 /unbind 解绑手表
 /refresh 刷新手表信息
 /getinfo 获取手表信息
 /zj [校验码] 自检算码
 /adb [校验码] adb算码
 /imfriendid 获取全部好友的imfriendid
 /send [对方imid] [内容] 向指定好友微聊发送消息
 /sendall [内容] 向全部好友微聊发送消息
 /help 显示此帮助
 Tips: web好友圈 http://bot.sourxe.team/moments
 Tips: xtc主板id购买、Bot Pro激活码可前往 https://shop.sourxe.team
当前页数 1/3""",
    2:
"""-----ZxeBot-----
 /getlikes 获取好友点赞列表
 /getlikes2 获取好友点赞列表(显示FriendID)
 /getkey 获取web好友圈登录密钥
 /likeall 自动全点主页
 /queueinfo 查询点赞队列状态
 /cancellike 取消全点主页操作
 /personalinfo 获取主页信息
 /addfriend 加好友(失效)
 /sign [个性签名] 更改个性签名
 /realname [新名称] 更改真实名称
 /name [新名称] 更改名称
 /step 修改步数
 /bgid 查看动态背景id
 /help 显示此帮助
Tips: Only V1
当前页数 2/3""",
    3:
"""-----ZxeBot-----
 /delmoment [数量] 删除指定数量的好友圈动态
 /moment 发送好友圈动态
 /momentblue 发送好友圈地名动态
 /momentpic [引用图片] 发送好友圈图片动态
 /momentvid [引用视频] 发送好友圈视频动态
 /bili [B站视频链接] 解析B站视频并发布到好友圈
 /hitokoto [背景id(可选)] 发送随机一言动态
 /momenturl [网址] [描述] 发送好友圈链接动态
 /sport50 修改运动50米时间
 /rope 修改1分钟跳绳数量
 /appsearch 应用商城应用搜索
-----权限管理-------
 /addpro [at] 提升用户权限
 /removepro [at] 移除用户权限
 /getcodes [数量] 生成指定数量的激活码
--------------------
 /about 关于这个机器人？
 /???
 /help 显示此帮助
Tips: Only V1
当前页数 3/3"""
}

@help_cmd.handle()
async def handle_help(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
    page_arg = args.extract_plain_text().strip()
    
    try:
        if page_arg:
            page_num = int(page_arg)
            if page_num < 1 or page_num > len(help_pages):
                await matcher.finish(f"页码无效！请输入 1-{len(help_pages)} 之间的数字")
        else:
            page_num = 1
    except ValueError:
        await matcher.finish("指令错误！请输入有效的页码数字")
        return
    await matcher.send(help_pages[page_num])

# ==================== 插件元信息 ====================
__plugin_name__ = "help"
__plugin_usage__ = """
命令列表：
/help - 显示第1页帮助
/help [页码] - 显示指定页码的帮助
"""