from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from bot import get_db_connection
from modules import im_client 
from modules import Apirequests
import asyncio
import time

sendall = on_command(
    "sendall", 
    aliases={}, 
    priority=10, 
    block=True
)

queueiminfo = on_command(
    "queueinfo2", 
    aliases={}, 
    priority=10, 
    block=True
)

# 存储用户确认状态
user_confirmations = {}
# 存储发送队列状态
sending_queues = {}

@sendall.handle()
async def sendall_start(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.send("请前往群聊使用Bot！")
        return
    
    driver = get_driver()
    allowed_groups = getattr(driver.config, 'allowed_groups', [])
    if allowed_groups and str(event.group_id) not in allowed_groups:
        return
    
    user_id = event.user_id
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await matcher.send("请输入正确的参数格式：/sendall 内容")
        return
    
    content = arg_text
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (user_id,))
            user_role = cursor.fetchone()
            
            if not user_role or user_role['role'] not in ['admin', 'donor']:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 权限不足！此功能仅对赞助者和管理员开放"))
                return

            cursor.execute("""
                SELECT d.watchid, d.chipid, d.bindnumber, d.model, d.imaccountid
                FROM devices_info d
                WHERE d.user_id = %s
            """, (user_id,))
            
            device_record = cursor.fetchone()

            if not device_record:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 您还没有绑定设备，请先使用 /bindwatch 命令绑定设备"))
                return
            
            if not device_record.get('imaccountid'):
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 未获取到imaccountid，请先使用 /refresh 命令刷新设备信息"))
                return
                
            watchid = device_record['watchid']
            chipid = device_record['chipid']
            bindnumber = device_record['bindnumber']
            imaccountid = device_record['imaccountid']
            model = device_record['model']
            
            friend_response = Apirequests.friendslist(watchid, bindnumber, chipid, model)
            
            if not (friend_response and friend_response.get('code') == '000001' and 'data' in friend_response):
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 获取好友列表失败，请稍后重试！"))
                return
                
            friend_list = friend_response['data']
            valid_friend_ids = [int(friend.get('imFriendId')) for friend in friend_list if friend.get('imFriendId') is not None]
            
            if not valid_friend_ids:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 您的好友列表为空，无法发送消息！"))
                return
            
            user_confirmations[user_id] = {
                'bindnumber': bindnumber,
                'watchid': watchid,
                'chipid': chipid,
                'imaccountid': imaccountid,
                'content': content,
                'friend_ids': valid_friend_ids,
                'group_id': event.group_id  # 添加群组ID用于后续@发送者
            }
            
            await matcher.send(Message(f"[CQ:at,qq={user_id}] 即将向 {len(valid_friend_ids)} 位好友发送消息：\n"
                                       f"内容：{content}\n"
                                       f"请确认是否继续？回复 \"确认发送\" 继续，回复其他内容取消。"))
            
    except Exception as e:
        await matcher.send(f"执行错误：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

async def send_single_message(bindnumber, watchid, chipid, friend_id, imaccountid, content):
    try:
        result = im_client.send_im_message(bindnumber, watchid, chipid, int(friend_id), int(imaccountid), content)
        return friend_id, result, None
    except Exception as e:
        return friend_id, False, str(e)

async def process_batch_send(user_id, user_data):
    bindnumber = user_data['bindnumber']
    watchid = user_data['watchid']
    chipid = user_data['chipid']
    imaccountid = user_data['imaccountid']
    content = user_data['content']
    friend_ids = user_data['friend_ids']
    group_id = user_data.get('group_id', None)  # 获取群组ID
    
    success_count = 0
    fail_count = 0
    failed_friends = []

    sending_queues[user_id] = {
        'start_time': time.time(),
        'end_time': None,
        'total_count': len(friend_ids),
        'current_progress': 0,
        'success_count': 0,
        'fail_count': 0,
        'failed_friends': [],
        'content': content,
        'status': 'running'
    }
    
    batch_size = 1
    for i in range(0, len(friend_ids), batch_size):
        batch_friend_ids = friend_ids[i:i+batch_size]
        
        # 创建当前批次的异步任务
        batch_tasks = []
        for friend_id in batch_friend_ids:
            task = send_single_message(bindnumber, watchid, chipid, friend_id, imaccountid, content)
            batch_tasks.append(task)
        
        # 异步执行当前批次
        batch_results = await asyncio.gather(*batch_tasks)
        
        # 处理当前批次结果
        for friend_id, result, error in batch_results:
            if result:
                success_count += 1
            else:
                fail_count += 1
                failed_friends.append(friend_id)
        
        # 更新队列状态
        sending_queues[user_id]['current_progress'] = min(i + batch_size, len(friend_ids))
        sending_queues[user_id]['success_count'] = success_count
        sending_queues[user_id]['fail_count'] = fail_count
        sending_queues[user_id]['failed_friends'] = failed_friends
        
        # 添加延迟避免过快请求
        if i + batch_size < len(friend_ids):
            await asyncio.sleep(0.1)  # 每批之间延迟0.5秒
    
    # 发送完成，更新状态
    sending_queues[user_id]['status'] = 'completed'
    sending_queues[user_id]['end_time'] = time.time()  # 记录完成时间
    
    # 发送完成后自动@发送者
    if group_id:
        from nonebot import get_bot
        try:
            bot = get_bot()
            completion_message = f"[CQ:at,qq={user_id}] 消息已全部发送完毕！\n"
            completion_message += f"成功：{success_count} 位好友\n"
            completion_message += f"失败：{fail_count} 位好友"
            await bot.send_group_msg(group_id=group_id, message=Message(completion_message))
        except Exception as e:
            # 如果自动@失败，不影响主流程
            pass
    
    return success_count, fail_count, failed_friends

@sendall.got("confirm")
async def sendall_confirm(event: MessageEvent, matcher: Matcher):
    user_id = event.user_id
    confirm_text = event.get_plaintext().strip()
    
    if user_id not in user_confirmations:
        return
    
    if confirm_text != "确认发送":
        del user_confirmations[user_id]
        await matcher.send("操作已取消")
        return
    
    user_data = user_confirmations[user_id]
    del user_confirmations[user_id]
    
    await matcher.send(Message(f"[CQ:at,qq={user_id}] 开始向 {len(user_data['friend_ids'])} 位好友发送消息... 您可以使用/queueinfo2 查询进度"))
    
    asyncio.create_task(process_batch_send(user_id, user_data))

@queueiminfo.handle()
async def queueiminfo_handler(event: MessageEvent, matcher: Matcher):
    if not isinstance(event, GroupMessageEvent):
        await matcher.send("请前往群聊使用Bot！")
        return
    
    driver = get_driver()
    allowed_groups = getattr(driver.config, 'allowed_groups', [])
    if allowed_groups and str(event.group_id) not in allowed_groups:
        await matcher.send("此群聊未授权，请前往授权群聊使用Bot！")
        return
    
    user_id = event.user_id
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (user_id,))
            user_role = cursor.fetchone()
            
            if not user_role or user_role['role'] not in ['admin', 'donor']:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 权限不足！此功能仅对赞助者和管理员开放"))
                return
    except Exception as e:
        await matcher.send(f"执行错误：{str(e)}")
        return
    finally:
        if 'conn' in locals():
            conn.close()
    
    if user_id not in sending_queues:
        await matcher.send(Message(f"[CQ:at,qq={user_id}] 当前没有正在进行的发送任务"))
        return
    
    queue_info = sending_queues[user_id]
    
    if queue_info['status'] == 'completed' and queue_info['end_time']:
        elapsed_time = queue_info['end_time'] - queue_info['start_time']
    else:
        elapsed_time = time.time() - queue_info['start_time']
    
    if queue_info['status'] == 'completed':
        status_message = f"[CQ:at,qq={user_id}] 微聊发送任务已完成\n"
        status_message += f"----------------------\n"
        status_message += f"内容：{queue_info['content']}\n"
        status_message += f"总数量：{queue_info['total_count']} 位\n"
        status_message += f"成功：{queue_info['success_count']} 位\n"
        status_message += f"失败：{queue_info['fail_count']} 位\n"
        
        if queue_info['failed_friends']:
            status_message += f"失败的好友ID：{queue_info['failed_friends'][:5]}" + ("..." if len(queue_info['failed_friends']) > 5 else "")
    else:
        progress_percent = (queue_info['current_progress'] / queue_info['total_count']) * 100
        estimated_remaining = (elapsed_time / queue_info['current_progress']) * (queue_info['total_count'] - queue_info['current_progress']) if queue_info['current_progress'] > 0 else 0
        
        status_message = f"[CQ:at,qq={user_id}] 微聊全列任务进行中\n"
        status_message += f"----------------------\n"
        status_message += f"内容：{queue_info['content']}\n"
        status_message += f"进度：{queue_info['current_progress']}/{queue_info['total_count']} ({progress_percent:.1f}%)\n"
        status_message += f"成功：{queue_info['success_count']} 位\n"
        status_message += f"失败：{queue_info['fail_count']} 位\n"
        status_message += f"已耗时：{elapsed_time:.1f} s\n"
        status_message += f"预计剩余：{estimated_remaining:.1f} s\n"
        status_message += f"状态：发送中..."
    
    await matcher.send(Message(status_message))

__plugin_name__ = "sendall"
__plugin_usage__ = """
批量发送IM消息插件

命令列表：
/sendall 内容 - 向所有好友发送内容（仅赞助者和管理员可用，需要二次确认）
/queueinfo2 - 查看当前发送队列状态
"""