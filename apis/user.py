#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import uuid
import bcrypt
import jwt
from utils.authentication import HTTPMethodView, ProtectedView, verify_token
from utils.exception import StandardResponseExc
from utils.authentication import generate_jwt, generate_email_code
from models.user import UserInfoTable
from exts import async_database
from cache import AllCache, RedisPoolContext
from settings.setting import cfgs


verification_codes = {}


class UserRegisterVerification(HTTPMethodView):
    async def post(self, request):
        email = request.json.get("email")
        if not email:
            raise StandardResponseExc(msg="Email is required")
        email = email.strip()

        async with async_database.aio_atomic():
            if await UserInfoTable.select(UserInfoTable.id).where(UserInfoTable.email == email).aio_exists():
                raise StandardResponseExc(msg="Email already registered")

        # TODO:限时发送
        code = generate_email_code()
        verification_codes[email] = code
        with RedisPoolContext() as r:
            r.set(f"user:register_code:{email}", code, ex=600)
        # print(f"验证码 {code} 发送至 {email}")  # 这里可替换为邮件发送逻辑
        return {"message": "Verification code sent"}


class UserRegisterView(HTTPMethodView):
    async def post(self, request):
        email = request.json.get("email")
        code = request.json.get("code")
        password = request.json.get("password")
        invite_code = request.json.get("invite_code")

        if not all([email, code, password]):
            raise StandardResponseExc(msg="Missing required fields")
        email = email.strip()
        code = code.strip()
        invite_code = invite_code.strip()

        if verification_codes.get(email) != code:
            raise StandardResponseExc(msg="Invalid verification code")

        redis_client = AllCache.get_client()
        cache_invite_code = redis_client.get(f"email:invite_code:{email}")
        if not cache_invite_code or (cache_invite_code != invite_code):
            raise StandardResponseExc(msg="Invalid invitation code")

        # TODO: 密码复杂度验证
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user_uuid = str(uuid.uuid4().hex)

        async with async_database.aio_atomic():
            if await UserInfoTable.select(UserInfoTable.id).where(UserInfoTable.email == email).aio_exists():
                raise StandardResponseExc(msg="Email already registered")

            await UserInfoTable.aio_create(
                uuid=user_uuid,
                email=email,
                password=hashed_password,
                invite_code=invite_code,
            )

        del verification_codes[email]  # 验证码使用后删除
        redis_client.delete(f"email:invite_code:{email}")
        redis_client.close()

        return {"message": "User registered successfully", "user_id": user_uuid}


class UserLoginView(HTTPMethodView):
    async def post(self, request):
        email = request.json.get("email")
        password = request.json.get("password")

        if not all([email, password]):
            raise StandardResponseExc(msg="Missing required fields")

        email = email.strip()
        try:
            db_user = await UserInfoTable.select().where(
                UserInfoTable.email == email).aio_get()
        except UserInfoTable.DoesNotExist:
            raise StandardResponseExc(msg="Invalid credentials")

        if not bcrypt.checkpw(password.encode(), db_user.password.encode()):
            raise StandardResponseExc(msg="Invalid credentials")

        token, exp_time, jti = generate_jwt(db_user)
        with RedisPoolContext() as r:
            r.set(f"user:{email}:jti", jti, ex=6*3600)

        return {"user_id": db_user.uuid, "token": token, "expires_at": exp_time}


class UserLogoutView(ProtectedView):
    need_auth = {"post": True}

    async def post(self, request):
        user = request.ctx.user

        # 将 token 加入黑名单，过期时间与 JWT 保持一致
        # await redis.setex(f"blacklist:{token}", int(exp_time - datetime.utcnow().timestamp()), "true")
        with RedisPoolContext() as r:
            # 单点登录
            r.delete(f"user:{user.email}:jti")

        # try:
        #     db_user = await UserInfoTable.select().where(
        #         UserInfoTable.email == user.email).aio_get()
        # except UserInfoTable.DoesNotExist:
        #     raise StandardResponseExc(msg="Invalid credentials")

        return {"message": "Logged out successfully", "user_id": user.user_id}
