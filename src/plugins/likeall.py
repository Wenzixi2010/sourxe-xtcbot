#!/usr/bin/env python3
"""
点赞所有好友
"""

import threading
from datetime import datetime
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message
from nonebot.matcher import Matcher
from nonebot import get_driver
from modules import Apirequests
from bot import get_db_connection

task_queue = []
current_task_id = None
previous_task_info = None
task_lock = threading.Lock()
global ok_count
likeall = on_command("likeall", aliases={}, priority=5, block=True)
queueinfo = on_command("queueinfo", aliases={}, priority=5, block=True)
cancellike = on_command("cancellike", aliases={}, priority=5, block=True)

def update_task_status(task_id, status, message=None, success_count=None, total_count=None):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            update_fields = ["status = %s"]
            params = [status]
            
            if message is not None:
                update_fields.append("message = %s")
                params.append(message)
            
            if success_count is not None:
                update_fields.append("success_count = %s")
                params.append(success_count)
            
            if total_count is not None:
                update_fields.append("total_count = %s")
                params.append(total_count)
            
            if status == 'processing':
                update_fields.append("started_at = %s")
                params.append(datetime.now())
            elif status in ['completed', 'failed']:
                update_fields.append("completed_at = %s")
                params.append(datetime.now())
            elif status == 'cancelled':
                update_fields.append("completed_at = %s")
                params.append(datetime.now())
            
            params.append(task_id)
            
            query = f"UPDATE likeall_tasks SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(query, params)
            conn.commit()
    except Exception as e:
        print(f"更新任务状态失败：{e}")
    finally:
        if 'conn' in locals():
            conn.close()

def get_queue_position(task_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM likeall_tasks 
                WHERE status = 'queued' 
                ORDER BY created_at ASC
            """)
            queued_tasks = cursor.fetchall()
            
            for i, task in enumerate(queued_tasks):
                if task['id'] == task_id:
                    return i + 1
            
            return 0
    except Exception as e:
        print(f"获取队列位置失败：{e}")
        return 0
    finally:
        if 'conn' in locals():
            conn.close()

def get_current_task_progress():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT success_count, total_count 
                FROM likeall_tasks 
                WHERE status = 'processing' 
                ORDER BY started_at DESC 
                LIMIT 1
            """)
            current_task = cursor.fetchone()
            
            if current_task and current_task['total_count']:
                return {
                    'success_count': current_task['success_count'] or 0,
                    'total_count': current_task['total_count']
                }
            return None
    except Exception as e:
        print(f"获取当前任务进度失败：{e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def get_previous_task_progress():
    global previous_task_info
    if previous_task_info:
        return previous_task_info
    return None

def process_likeall_task(task_id, user_id, watchid, bindnumber, chipid, model):
    global current_task_id, task_queue, previous_task_info
    
    try:
        friends_response = Apirequests.friendslist(watchid, bindnumber, chipid, model)
        if not friends_response or friends_response.get('code') != '000001':
            update_task_status(task_id, 'failed', '获取好友列表失败')
            return
        
        friends_data = friends_response.get('data', [])
        total_friends = len(friends_data)
        success_count = 0
        ok_count = 0
        
        update_task_status(
            task_id, 
            'processing', 
            f'正在点赞，共{total_friends}个好友',
            0,
            total_friends
        )
        
        for result in Apirequests.likeall(watchid, bindnumber, chipid, model):
            # 检查任务是否被取消
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT status FROM likeall_tasks WHERE id = %s", (task_id,))
                task = cursor.fetchone()
                if task and task['status'] == 'cancelled':
                    update_task_status(task_id, 'cancelled', '任务已被用户取消')
                    return
            conn.close()
            
            if result.get('success'):
                success_count += 1
            ok_count += 1
            
            update_task_status(
                task_id,
                'processing',
                f'正在点赞，已处理{ok_count}/{total_friends}个好友',
                success_count,
                total_friends
            )
        
        previous_task_info = {
            'user_id': user_id,
            'success_count': success_count,
            'total_count': total_friends,
            'completed_at': datetime.now()
        }
        
        update_task_status(
            task_id,
            'completed',
            f'点赞完成，成功{success_count}个，共{total_friends}个好友',
            success_count,
            total_friends
        )
    
    except Exception as e:
        update_task_status(task_id, 'failed', f'执行出错: {str(e)}')
    
    finally:
        with task_lock:
            current_task_id = None
            if task_queue:
                next_task = task_queue.pop(0)
                current_task_id = next_task['task_id']
                threading.Thread(
                    target=process_likeall_task,
                    args=(next_task['task_id'], next_task['user_id'], 
                          next_task['watchid'], next_task['bindnumber'], 
                          next_task['chipid'], next_task['model'])
                ).start()

@likeall.handle()
async def handle_likeall(event: MessageEvent, matcher: Matcher):
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
    global current_task_id, task_queue

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
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_info (user_id, role, created_at, last_login) 
                VALUES (%s, 'user', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
                ON DUPLICATE KEY UPDATE last_login = CURRENT_TIMESTAMP
            """, (user_id,))
            
            cursor.execute("""
                SELECT d.watchid, d.chipid, d.bindnumber, d.model 
                FROM devices_info d
                WHERE d.user_id = %s
            """, (user_id,))
            
            device_record = cursor.fetchone()
            
            if not device_record:
                await matcher.send("您还没有绑定设备，请先使用 /bindwatch 命令绑定设备（直接发送后面不用跟参数）")
                return
            
            cursor.execute("""
                SELECT id, status FROM likeall_tasks 
                WHERE user_id = %s AND status IN ('queued', 'processing')
            """, (user_id,))
            
            existing_task = cursor.fetchone()
            if existing_task:
                await matcher.send("您已有一个点赞任务在执行或排队中，请勿重复提交")
                return
            
            watchid = device_record['watchid']
            chipid = device_record['chipid']
            bindnumber = device_record['bindnumber']
            model = device_record['model']
            
            cursor.execute("""
                INSERT INTO likeall_tasks (user_id, status, message) 
                VALUES (%s, 'queued', '任务已加入队列')
            """, (user_id,))
            
            task_id = cursor.lastrowid
            conn.commit()
            
            with task_lock:
                if current_task_id is None:
                    current_task_id = task_id
                    update_task_status(task_id, 'processing', '任务开始执行')
                    threading.Thread(
                        target=process_likeall_task,
                        args=(task_id, user_id, watchid, bindnumber, chipid, model)
                    ).start()
                    await matcher.send("点赞任务已开始执行，请稍后使用 /queueinfo 查询进度")
                else:
                    task_info = {
                        'task_id': task_id,
                        'user_id': user_id,
                        'watchid': watchid,
                        'chipid': chipid,
                        'bindnumber': bindnumber,
                        'model': model
                    }
                    task_queue.append(task_info)
                    
                    queue_position = get_queue_position(task_id)
                    current_progress = get_current_task_progress()
                    progress_msg = ""
                    if current_progress:
                        progress_msg = f" ({ok_count}/{current_progress['total_count']})"
                    
                    update_task_status(
                        task_id,
                        'queued',
                        f'任务已加入队列，前方还有{queue_position}位用户'
                    )
                    
                    await matcher.send(f"点赞任务已加入队列，您前方还有{queue_position}位用户, 您可用使用/queueinfo查询队列状态")
    
    except Exception as e:
        print(f"数据库操作失败：{e}")
        await matcher.send(f"命令执行失败 {e}")
    finally:
        if 'conn' in locals():
            conn.close()

@cancellike.handle()
async def handle_cancellike(event: MessageEvent, matcher: Matcher):
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("请前往群聊使用Bot！(SourXe BotGroup: 1063758858)")
        return
    
    user_id = event.user_id
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 查找用户正在进行或排队中的任务
            cursor.execute("""
                SELECT id, status FROM likeall_tasks 
                WHERE user_id = %s AND status IN ('queued', 'processing')
            """, (user_id,))
            
            task = cursor.fetchone()
            
            if not task:
                await matcher.send("您当前没有正在进行或排队中的点赞任务")
                return
            
            task_id = task['id']
            status = task['status']
            
            # 取消任务
            if status == 'queued':
                # 如果任务还在队列中，直接从队列中移除
                global task_queue
                with task_lock:
                    task_queue = [t for t in task_queue if t['task_id'] != task_id]
                update_task_status(task_id, 'cancelled', '任务已被用户取消')
                await matcher.send("已成功取消您的点赞任务")
            elif status == 'processing':
                # 如果任务正在执行，标记为取消状态
                update_task_status(task_id, 'cancelled', '任务已被用户取消')
                await matcher.send("已发送取消请求，任务将在下一个检查点被取消")
    
    except Exception as e:
        print(f"取消任务失败：{e}")
        await matcher.send(f"取消任务失败：{e}")
    finally:
        if 'conn' in locals():
            conn.close()

@queueinfo.handle()
async def handle_queueinfo(event: MessageEvent, matcher: Matcher):
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("请前往群聊使用Bot！(SourXe BotGroup: 1063758858)")
        return
    user_id = event.user_id
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, status, message, success_count, total_count, 
                       created_at, started_at, completed_at
                FROM likeall_tasks 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (user_id,))
            
            task = cursor.fetchone()
            
            if not task:
                await matcher.send("您没有提交过点赞任务")
                return
            
            task_id = task['id']
            status = task['status']
            message = task['message']
            success_count = task['success_count']
            total_count = task['total_count']
            
            if status == 'queued':
                queue_position = get_queue_position(task_id)
                current_progress = get_current_task_progress()
                progress_msg = ""
                if current_progress:
                    progress_msg = f" ({current_progress['success_count']}/{current_progress['total_count']})"
                
                if queue_position > 0:
                    await matcher.send(f"您的点赞任务正在排队中\n前方还有{queue_position}位用户{progress_msg}")
                else:
                    await matcher.send("您的点赞任务正在排队中")
            
            elif status == 'processing':
                await matcher.send(f"您的点赞任务正在执行中\n{message}\n成功: {success_count}/{total_count}")
            
            elif status == 'completed':
                completion_time = task['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if task['completed_at'] else '未知'
                await matcher.send(f"您的点赞任务已完成\n{message}\n完成时间: {completion_time}")
            
            elif status == 'failed':
                completion_time = task['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if task['completed_at'] else '未知'
                await matcher.send(f"您的点赞任务执行失败\n{message}\n失败时间: {completion_time}")
            
            elif status == 'cancelled':
                completion_time = task['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if task['completed_at'] else '未知'
                await matcher.send(f"您的点赞任务已被取消\n{message}\n终止时间: {completion_time}")
    
    except Exception as e:
        print(f"数据库操作失败：{e}")
        await matcher.send(f"命令执行失败 {e}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "likeall"
__plugin_usage__ = """
点赞所有好友插件 - 排队执行版本

命令列表：
/likeall - 提交点赞所有好友的任务
/queueinfo - 查询您的点赞任务状态
/cancellike - 取消正在进行或排队中的点赞任务
"""