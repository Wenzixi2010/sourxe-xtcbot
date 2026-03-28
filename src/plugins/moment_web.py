import os
import traceback
import json
import secrets
from datetime import datetime, timedelta
from nonebot import get_driver
from nonebot.plugin import PluginMetadata
from fastapi import FastAPI, Request, Form, Response, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from bot import get_db_connection
from modules import Apirequests

__plugin_meta__ = PluginMetadata(
    name="好友圈Web应用",
    description="好友圈浏览Web应用",
    usage="访问 /moments 使用好友圈功能",
    type="application"
)

driver = get_driver()
app: FastAPI = driver.server_app

moment_static_dir = "moment/static"
if os.path.exists(moment_static_dir):
    app.mount("/moments/static", StaticFiles(directory=moment_static_dir), name="moment_static")

moment_templates_dir = "moment/templates"
if os.path.exists(moment_templates_dir):
    templates = Jinja2Templates(directory=moment_templates_dir)
else:
    templates = Jinja2Templates(directory="templates")

async def get_user_id_by_token(token: str) -> int:
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_id FROM moment_temp_tokens 
                WHERE token = %s AND expires_at > NOW()
            """, (token,))
            result = cursor.fetchone()
            if result:
                return result[0] if isinstance(result, tuple) else result['user_id']
            return None
    except Exception as e:
        print(f"获取token对应user_id失败：{e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

async def verify_temp_token(token: str) -> bool:
    user_id = await get_user_id_by_token(token)
    return user_id is not None

async def create_temp_token(user_id: int = None):
    token = secrets.token_hex(8)
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            expires_at = datetime.now() + timedelta(hours=1)
            if user_id:
                cursor.execute("""
                    INSERT INTO moment_temp_tokens (user_id, token, expires_at)
                    VALUES (%s, %s, %s)
                """, (user_id, token, expires_at))
            else:
                cursor.execute("""
                    INSERT INTO moment_temp_tokens (token, expires_at)
                    VALUES (%s, %s)
                """, (token, expires_at))
            conn.commit()
            return token
    except Exception as e:
        print(f"创建临时密钥失败：{e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

async def parse_moment_data(moment_data):
    try:
        watch_name = moment_data.get('watchName')
        if not watch_name and moment_data.get('comments'):
            for comment in moment_data['comments']:
                if comment.get('watchName'):
                    watch_name = comment['watchName']
                    break
        if not watch_name:
            watch_name = "未知用户"
        
        content = moment_data.get('content', '')
        moment_content = ''
        download_urls = []
        video_urls = []
        
        # 处理content字段（JSON格式）
        if content.strip().startswith('{') and content.strip().endswith('}'):
            try:
                content_data = json.loads(content)
                moment_content = content_data.get('content', '')
                
                # 不再处理icon作为封面图
                
                # 只处理source（视频）
                if 'source' in content_data and content_data['source'] and 'downloadUrl' in content_data['source']:
                    video_url = content_data['source']['downloadUrl']
                    if video_url:
                        video_urls.append(video_url)
                        # 视频URL也添加到images数组，以确保前端能正确显示
                        download_urls.append(video_url)
            except json.JSONDecodeError:
                moment_content = content
        else:
            moment_content = content
            
        # 从resource字段补充信息
        resource = moment_data.get('resource')
        if resource and isinstance(resource, str) and resource.strip().startswith('{') and resource.strip().endswith('}'):
            try:
                resource_data = json.loads(resource)
                # 这里可以根据需要补充处理resource中的信息
            except json.JSONDecodeError:
                pass
        
        if not moment_content:
            moment_content = "无内容"
        
        comments = []
        if moment_data.get('comments'):
            for comment in moment_data['comments']:
                comments.append({
                    'watchName': comment.get('watchName', '未知用户'),
                    'comment': comment.get('comment', ''),
                    'createTime': comment.get('createTime', '')
                })
        
        like_count = moment_data.get('likeTotal', moment_data.get('likeCount', 0))
        comment_count = len(comments)
        publish_time = moment_data.get('createTime', moment_data.get('gmtCreate', ''))
        
        result = {
            'id': moment_data.get('id', moment_data.get('momentId', '')),
            'nickname': watch_name,
            'content': moment_content,
            'images': download_urls,
            'videos': video_urls,
            'time': publish_time,
            'like_count': like_count,
            'comment_count': comment_count,
            'comments': comments
        }
        
        # 添加原始数据中的其他重要字段
        if moment_data.get('momentId'):
            result['momentId'] = moment_data['momentId']
        if moment_data.get('type'):
            result['type'] = moment_data['type']
        
        return result
    except Exception as e:
        print(f"解析动态数据错误：{e}")
        print(traceback.format_exc())
        return None

async def get_user_device_info(user_id: int):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT d.watchid, d.bindnumber, d.chipid, d.model
                FROM devices_info d
                WHERE d.user_id = %s
                LIMIT 1
            """, (user_id,))
            device_record = cursor.fetchone()
            if device_record:
                if isinstance(device_record, dict):
                    return device_record
                else:
                    return {
                        'watchid': device_record[0],
                        'bindnumber': device_record[1],
                        'chipid': device_record[2],
                        'model': device_record[3]
                    }
            else:
                print(f"未找到用户{user_id}的设备信息")
                return None
    except Exception as e:
        print(f"获取用户设备信息失败：{str(e)}")
        print(traceback.format_exc())
        return None
    finally:
        if 'conn' in locals():
            conn.close()

async def get_first_device_info():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT d.watchid, d.bindnumber, d.chipid, d.model
                FROM devices_info d
                LIMIT 1
            """)
            device_record = cursor.fetchone()
            if device_record:
                if isinstance(device_record, dict):
                    return device_record
                else:
                    return {
                        'watchid': device_record[0],
                        'bindnumber': device_record[1],
                        'chipid': device_record[2],
                        'model': device_record[3]
                    }
            else:
                print("未找到任何设备信息")
                return None
    except Exception as e:
        print(f"获取设备信息失败：{str(e)}")
        print(traceback.format_exc())
        return None
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/moments/login", response_class=HTMLResponse)
async def moment_login_page(request: Request):
    try:
        return templates.TemplateResponse("login.html", {"request": request})
    except Exception as e:
        print(f"加载登录页面失败：{e}")
        return HTMLResponse(content="<h1>页面加载失败</h1>", status_code=500)

@app.post("/api/moments/login")
async def moment_login(key: str = Form(...)):
    try:
        if await verify_temp_token(key):
            return JSONResponse({
                "ok": True, 
                "msg": "登录成功",
                "redirect_url": f"/moments?key={key}"
            })
        else:
            return JSONResponse({
                "ok": False, 
                "msg": "密钥错误，或密钥已过期"
            })
    except Exception as e:
        print(f"登录API错误：{e}")
        return JSONResponse({
            "ok": False, 
            "msg": "服务器内部错误"
        }, status_code=500)

@app.get("/moments", response_class=HTMLResponse)
async def moment_index(request: Request, key: str = Query(None)):
    try:
        if key and await verify_temp_token(key):
            return templates.TemplateResponse("index.html", {
                "request": request,
                "key": key,
                "templateVars": {"key": key}
            })
        else:
            return RedirectResponse(url="/moments/login")
    except Exception as e:
        print(f"加载主页失败：{e}")
        return HTMLResponse(content="<h1>页面加载失败</h1>", status_code=500)

@app.get("/api/moments/data")
async def get_moments_data(request: Request, page: int = Query(1, ge=1), offset: int = Query(0), key: str = Query(None)):
    try:
        if not key:
            return JSONResponse(
                {"ok": False, "error": "未授权访问", "moments": []}, 
                status_code=401
            )
        
        # 获取token对应的user_id
        user_id = await get_user_id_by_token(key)
        if not user_id:
            return JSONResponse(
                {"ok": False, "error": "未授权访问", "moments": []}, 
                status_code=401
            )
        
        # 获取该用户的设备信息
        device_record = await get_user_device_info(user_id)
        
        # 如果没有该用户的设备信息，尝试获取第一个设备信息
        if not device_record:
            device_record = await get_first_device_info()
            if not device_record:
                return JSONResponse({
                    'ok': False,
                    'error': '暂无设备信息',
                    'moments': []
                })
        
        watchid = device_record['watchid']
        bind_number = device_record['bindnumber']
        chipid = device_record['chipid']
        model = device_record['model']
        
        try:
            current_page = page if page > 0 else (offset // 20) + 1
            response = Apirequests.momentview(watchid, bind_number, chipid, model, current_page)
            
            # 安全检查response
            if not response:
                return JSONResponse({
                    'ok': False,
                    'error': '网络错误，未收到响应',
                    'moments': []
                })
            
            # 安全检查code和data
            if response.get('code') == '000001':
                # 确保watch_moments始终是可迭代对象
                data = response.get('data', {})
                watch_moments = data.get('watchMoments', []) if data else []
                
                parsed_moments = []
                # 再次确认watch_moments是可迭代的
                if isinstance(watch_moments, (list, tuple)):
                    for moment_data in watch_moments:
                        result = await parse_moment_data(moment_data)
                        if result:
                            parsed_moments.append(result)
                
                return JSONResponse({
                    'ok': True,
                    'moments': parsed_moments,
                    'hasMore': isinstance(watch_moments, (list, tuple)) and len(watch_moments) >= 20,
                    'page': current_page
                })
            else:
                error_msg = response.get('desc', '未知错误')
                return JSONResponse({
                    'ok': False,
                    'error': error_msg,
                    'moments': []
                })
        except Exception as e:
            print(f"调用Apirequests.momentview失败：{str(e)}")
            print(traceback.format_exc())
            return JSONResponse({
                'ok': False,
                'error': f'API调用失败：{str(e)}',
                'moments': []
            })
            
    except Exception as e:
        print(f"获取动态数据错误：{str(e)}")
        print(traceback.format_exc())
        return JSONResponse({
            'ok': False,
            'error': '服务器内部错误',
            'moments': []
        }, status_code=500)

@app.get("/api/moments")
async def api_moments_redirect(request: Request, page: int = Query(1, ge=1), key: str = Query(None)):
    url_params = f"page={page}"
    if key:
        url_params += f"&key={key}"
    return RedirectResponse(url=f"/api/moments/data?{url_params}")

@driver.on_startup
async def startup():
    print("好友圈Web应用已启动")