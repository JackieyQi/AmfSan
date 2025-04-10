#! /usr/bin/python
# coding:utf8

from sanic import Sanic, response
import ujson as json
from sanic.response import json as json_view
from sanic.handlers import ErrorHandler
from sanic_ext import Extend

app = Sanic(name=__name__)
Extend(app, config={
    "CORS_ORIGINS": "*",
    "CORS_ALLOW_METHODS": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "CORS_ALLOW_HEADERS": ["Content-Type", "Authorization"],
    "CORS_ALLOW_CREDENTIALS": True,
})

from settings.setting import cfgs
from cache import AllCache
from cache.plot import APIRequestCountCache

app.config.update(cfgs)
redis_client = AllCache.get_client()

# from exts import database
# @app.middleware('request')
# async def handle_request(request):
#     if database.is_closed():
#         database.connect()
#
#
# @app.middleware('response')
# async def handle_response(request, response):
#     if not database.is_closed():
#         database.close()


banned_ips_key = "banned_ips"


@app.exception(Exception)
async def handle_404s(request, exception):
    if exception.status_code == 404:
        client_ip = request.ip
        redis_client.sadd(banned_ips_key, client_ip)
        return response.text("MAGA", status=200)
    return response.text("MAGA", status=200)


@app.middleware("request")
async def check_banned_ips(request):
    client_ip = request.ip
    if redis_client.sismember(banned_ips_key, client_ip):
        return response.text("MAGA", status=200)


@app.middleware("request")
async def parse_request_params(request):
    api_count = APIRequestCountCache.get()
    if not api_count:
        APIRequestCountCache.set(1, ex=60)
    else:
        if int(api_count) > 100:
            return "success"
        else:
            APIRequestCountCache.incr()

    request.form.update(request.args)
    try:
        _body = json.loads(request.body)
        request.form.update({
            k: [json.dumps(v) if isinstance(v, (list, dict)) else str(v)] for k, v in _body.items()
        })
    except:
        pass


@app.middleware("response")
async def parse_response_body(request, response):
    if isinstance(response, (list, dict, str, int)):
        return json_view({
            "code": 0,
            "message": "",
            "data": response
        })


from utils.exception import StandardResponseExc, UnAuthorizationExc


class CustormErrorHandler(ErrorHandler):
    def default(self, request, exception):
        if isinstance(exception, StandardResponseExc):
            return json_view({"code": exception.code, "message": exception.message, "data": exception.data})
        elif isinstance(exception, UnAuthorizationExc):
            return json_view({"code": exception.code, "message": exception.message})

        return super().default(request, exception)


app.error_handler = CustormErrorHandler()

from apis import urls_bp

for _val in urls_bp:
    _view, _uri = _val
    app.add_route(_view, _uri)
