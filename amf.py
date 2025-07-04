#! /usr/bin/python
# coding:utf8

from sanic import Sanic, response
import ujson as json
import logging.config
from sanic.response import json as json_view
from sanic.handlers import ErrorHandler
from sanic_ext import Extend

from settings.setting import cfgs
from settings.log import LOG_SANIC_CONF
from cache import AllCache
from cache.plot import APIRequestCountCache
from exts import DatabaseConnectionManager
from utils.exception import StandardResponseExc, UnAuthorizationExc

app = Sanic(name=__name__)
Extend(app, config={
    "CORS_ORIGINS": "*",
    "CORS_ALLOW_METHODS": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "CORS_ALLOW_HEADERS": ["Content-Type", "Authorization"],
    "CORS_ALLOW_CREDENTIALS": True,
})

app.config.update(cfgs)
logging.config.dictConfig(LOG_SANIC_CONF)

redis_client = AllCache.get_client()

# 优化后的数据库连接中间件
@app.middleware('request')
async def ensure_database_connection(request):
    """确保数据库连接可用"""
    try:
        # 预热数据库连接
        DatabaseConnectionManager.get_async_database()
        # 在请求上下文中存储数据库连接状态
        request.ctx.db_available = True
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"数据库连接检查失败: {e}")
        request.ctx.db_available = False


@app.middleware('response')
async def cleanup_request_resources(request, response):
    """清理请求相关资源"""
    # 这里可以添加请求级别的资源清理逻辑
    # 比如关闭临时连接、清理缓存等
    pass


banned_ips_key = "banned_ips"


@app.exception(Exception)
async def handle_exceptions(request, exception):
    """改进的异常处理，增加安全性"""
    logger = logging.getLogger(__name__)
    
    # 记录异常详情
    logger.error(f"请求异常: {type(exception).__name__}: {str(exception)}")
    
    # 对于404错误的特殊处理
    if getattr(exception, 'status_code', None) == 404:
        client_ip = request.ip
        try:
            redis_client.sadd(banned_ips_key, client_ip)
            logger.warning(f"IP {client_ip} 触发404，已加入封禁列表")
        except Exception as e:
            logger.error(f"添加封禁IP失败: {e}")
        
        return response.json({"error": "Not Found"}, status=404)
    
    # 数据库连接相关错误
    if "database" in str(exception).lower() or "mysql" in str(exception).lower():
        logger.error("数据库相关错误，尝试重新建立连接")
        return response.json({"error": "Database temporarily unavailable"}, status=503)
    
    # 默认错误响应
    return response.json({"error": "Internal Server Error"}, status=500)


@app.middleware("request")
async def check_banned_ips(request):
    """检查封禁IP"""
    client_ip = request.ip
    try:
        if redis_client.sismember(banned_ips_key, client_ip):
            return response.json({"error": "Access Denied"}, status=403)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"检查封禁IP失败: {e}")
        # 如果Redis不可用，允许请求继续


@app.middleware("request")
async def parse_request_params(request):
    """解析请求参数并进行限流"""
    try:
        api_count = APIRequestCountCache.get()
        if not api_count:
            APIRequestCountCache.set(1, ex=60)
        else:
            if int(api_count) > 100:
                return response.json({"error": "Rate limit exceeded"}, status=429)
            else:
                APIRequestCountCache.incr()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"限流检查失败: {e}")
        # 如果缓存不可用，允许请求继续

    # 解析请求参数
    request.form.update(request.args)
    try:
        if request.body:
            _body = json.loads(request.body)
            request.form.update({
                k: [json.dumps(v) if isinstance(v, (list, dict)) else str(v)] for k, v in _body.items()
            })
    except BaseException as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"请求体解析失败: {e}")
        # 解析失败时继续处理，不阻止请求


@app.middleware("response")
async def parse_response_body(request, response):
    """标准化响应格式"""
    if isinstance(response, (list, dict, str, int)):
        return json_view({
            "code": 0,
            "message": "success",
            "data": response
        })


class CustormErrorHandler(ErrorHandler):
    def default(self, request, exception):
        logger = logging.getLogger(__name__)
        
        if isinstance(exception, StandardResponseExc):
            return json_view({
                "code": exception.code, 
                "message": exception.message, 
                "data": exception.data
            })
        elif isinstance(exception, UnAuthorizationExc):
            return json_view({
                "code": exception.code, 
                "message": exception.message
            })

        # 记录未处理的异常
        logger.error(f"未处理的异常: {type(exception).__name__}: {str(exception)}")
        return super().default(request, exception)


app.error_handler = CustormErrorHandler()

from apis import urls_bp

for _val in urls_bp:
    _view, _uri = _val
    app.add_route(_view, _uri)


# 应用关闭时的清理工作
@app.before_server_stop
async def cleanup_resources(app, loop):
    """应用关闭前清理资源"""
    logger = logging.getLogger(__name__)
    logger.info("开始清理应用资源...")
    
    try:
        # 关闭数据库连接
        DatabaseConnectionManager.close_all_connections()
        logger.info("数据库连接已清理")
    except Exception as e:
        logger.error(f"清理数据库连接时出错: {e}")
    
    try:
        # 关闭Redis连接
        redis_client.close()
        logger.info("Redis连接已清理")
    except Exception as e:
        logger.error(f"清理Redis连接时出错: {e}")
    
    logger.info("应用资源清理完成")
