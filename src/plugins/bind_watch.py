#!/usr/bin/env python3
"""
绑定手表
"""

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, MessageEvent, GroupMessageEvent, PrivateMessageEvent
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from modules import Apirequests
from nonebot import get_driver

from bot import get_db_connection

bind_watch = on_command(
    "bindwatch", 
    aliases={}, 
    priority=10, 
    block=True, 
    state={"timeout": 15})

@bind_watch.handle()
async def bind_watch_start(event: MessageEvent, matcher: Matcher, state: T_State):
    if not isinstance(event, PrivateMessageEvent):
        await matcher.finish("请前往私聊界面执行该命令！")
        return
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
    user_id = event.user_id
    state["user_id"] = user_id
    await matcher.send("""欢迎您访问并使用由SourXe XTCBOT提供的服务（以下简称“本项目”）。在继续使用本服务之前，请务必逐字逐句阅读并充分理解本《最终用户许可协议》（以下简称“本协议”）。本协议是一份具有法律约束力的合同，适用于您（以下可称“您”“用户”）与 SourXe XTCBOT运营方（以下简称“我们”）之间就您使用本服务所建立的全部法律关系。一旦您进行下一步操作或实际使用本服务，即视为您已阅读、理解并接受本协议的全部条款，且同意以后所有的更新、修改之后的条款。若您不同意本协议的任何内容，请立即停止使用本服务并注销账户。
本服务所包含的全部技术知识产权均归管理方或相关权利人所有。 使用限制   未经管理方书面许可，任何单位或个人不得以任何形式进行使用、复制、修改、传播、出售、或基于本服务开发衍生产品。 
1.免责声明
1.1我们不会擅自利用您的信息进行违法犯罪行为，且SourXe管理组将承诺不会将您上传至本服务数据库的私人信息泄露。
1.2本项目为SourXe开发，闭源公益项目，任何人禁止在无管理组调整的情况下收费，否则均为诈骗，且与本项目和本项目开发者管理组无任何关系，我们概不承担任何责任。
1.3您所上传的数据都是您自己自愿而为，如果您非自愿，请立即退出并删除此XTCBOT的机器人QQ。
1.4您所使用的功能皆有开发者开发，且功能也许会有缺陷，bug，但并不为本项目开发者意愿所为，仅为概率问题。
1.5本项目属于“外挂类”项目，功能使用难免会被官方包括但不限于控制，删除等，与本项目及开发者无任何关系且我们不承担任何责任。
1.6在此条款有更新、调整时，默认您同意此条款。
2.欢迎您使用XTCBOT BySourXe
                                SourXeiMoo管理组
                             2025年10月2日第一版""")
    await matcher.send("开始绑定手表\n"
                      "请直接发送手表的 chipid：")


@bind_watch.got("chipid")
async def got_chipid(event: MessageEvent, matcher: Matcher, state: T_State):
    chipid = str(event.get_message()).strip()
    if not chipid:
        await matcher.reject("chipid 不能为空，请重新输入：")
    state["chipid"] = chipid
    state["step"] = "waiting_bindnumber"
    
    await matcher.send("chipid已保存！\n"
                      "接下来请发送绑定号：")


@bind_watch.got("bindnumber")
async def got_bindnumber(event: MessageEvent, matcher: Matcher, state: T_State):
    bindnumber = str(event.get_message()).strip()
    if not bindnumber:
        await matcher.reject("绑定号不能为空，请重新输入：")
    
    user_id = state["user_id"]
    chipid = state["chipid"]
    
    response = Apirequests.get_info(bindnumber, chipid)
    if response['code'] ==  '000001':
        try:
            conn = get_db_connection() 
            with conn.cursor() as cursor:

                cursor.execute("""
                    INSERT INTO user_info (user_id, role, created_at, last_login) 
                    VALUES (%s, 'user', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
                    ON DUPLICATE KEY UPDATE last_login = CURRENT_TIMESTAMP
                """, (user_id,))

                cursor.execute("""
                    SELECT id FROM devices_info WHERE user_id = %s
                """, (user_id,))
                
                existing_record = cursor.fetchone()
                watchid = response['data']['id']
                model = response['data']['innerModel']
                imaccountid = response['data']['imAccountInfo']['imAccountId']
                
                if existing_record:
                    cursor.execute("""
                        UPDATE devices_info 
                        SET watchid = %s, chipid = %s, bindnumber = %s, model = %s, imaccountid = %s
                        WHERE user_id = %s
                    """, (
                        watchid,
                        chipid,
                        bindnumber,
                        model,
                        imaccountid,
                        user_id
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO devices_info (user_id, watchid, chipid, bindnumber, model, imaccountid) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        user_id,
                        watchid,
                        chipid,
                        bindnumber,
                        model,
                        imaccountid
                    ))
                
                conn.commit()
                            
        except Exception as e:
            print(f"数据库操作失败：{e}")
            await matcher.finish(f"命令执行失败 {e}")
            return
        finally:
            conn.close()
        await matcher.send(f"这是返回的设备信息，请确认是否正确！如不正确请重新绑定\n"
                            f"返回码：{response['code']}\n"
                            f"Info：{response['desc']}\n"
                            f"---------------------------\n"
                            f"watchID：{response['data']['id']}\n"
                            f"imaccountID：{imaccountid}\n"
                            f"名称：{response['data']['name']}\n"
                            f"机型：{response['data']['model']}\n"
                            f"系统版本：{response['data']['firmware']}\n"
                            f"属地：{response['data']['pushProvince']}\n"
                            f"电量：{response['data']['battery']}%\n"
                            f"在线状态：{response['data']['watchOnline']}\n"
                            f"欢迎您使用XTCBOT BySourXe"
                            )
    else:
        await matcher.send(f"获取设备信息失败！\n"
                            f"----------------------\n"
                            f"返回码：{response['code']}\n"
                            f"Info：{response['desc']}\n")

# ==================== 插件元信息 ====================
__plugin_name__ = "bind_watch"
__plugin_usage__ = """
绑定手表插件

命令列表：
/bindwatch 或 /绑定手表 - 开始绑定手表
"""