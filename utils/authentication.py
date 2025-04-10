#! /usr/bin/env python
# coding:utf8

import uuid
import jwt
import string
import random
from datetime import datetime, timedelta
from sanic.views import HTTPMethodView

from cache import RedisPoolContext
from settings.setting import cfgs


# from rest_framework.authentication import BaseAuthentication


# class RedisTokenAuth(BaseAuthentication):
# def authenticate(self, request):
# pass

class UserContext:
    def __init__(self, payload: dict):
        self.user_id = payload.get("user_id")
        self.email = payload.get("email")
        self.exp = payload.get("exp")
        self.role = payload.get("role", "user")  # 可扩展字段

    def is_admin(self):
        return self.role == "admin"


def verify_token(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, cfgs["secret_key"], algorithms=["HS256"])
        email = payload.get("email")
        jti = payload.get("jti")

        with RedisPoolContext() as r:
            cache = r.get(f"user:{email}:jti")
            if not cache:
                return None
            if cache != jti:
                return None

        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


class ProtectedView(HTTPMethodView):
    """
    自定义 HTTPMethodView，实现每个方法级别的 JWT 权限控制
    示例：need_auth = {"get": False, "post": True}
    """
    need_auth = {}

    async def dispatch_request(self, request, *args, **kwargs):
        method = request.method.lower()

        if self.need_auth.get(method, False):
            payload = verify_token(request)
            if not payload:
                return {"message": "Unauthorized", "code": 401}
            request.ctx.user = UserContext(payload)  # 存储用户信息，可用于后续方法内访问

        handler = getattr(self, method, None)
        if not handler:
            return {"error": f"Method {method.upper()} not allowed", "status": 405}
        return await handler(request, *args, **kwargs)


def generate_jwt(user):
    exp_time = datetime.now() + timedelta(hours=6)
    jti = uuid.uuid4().hex
    payload = {
        "user_id": user.uuid,
        "email": user.email,
        "exp": exp_time,
        "jti": jti
    }
    token = jwt.encode(payload, cfgs["secret_key"], algorithm="HS256")
    return token, exp_time.timestamp(), jti


def generate_email_code():
    return "".join(random.choices(string.digits, k=6))
