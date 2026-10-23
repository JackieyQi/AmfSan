"""User-owned strategy persistence; saving never activates a monitoring strategy."""
import json
import time
from models.user import UserStrategyTable
from models.custom_strategy import validate_strategy
from utils.exception import StandardResponseExc


def serialize(row):
    return {"id": row.id, "version": row.version,
            "definition": json.loads(row.definition), "update_ts": row.update_ts}


async def list_strategies(user_id):
    rows = await UserStrategyTable.select().where(
        UserStrategyTable.user_id == user_id
    ).order_by(UserStrategyTable.create_ts.desc(), UserStrategyTable.id).aio_execute()
    return [serialize(row) for row in rows]


async def save_strategy(user_id, payload):
    if not isinstance(payload, dict) or set(payload) - {"id", "version", "definition"}:
        raise StandardResponseExc(msg="请求格式不正确")
    try:
        definition = validate_strategy(payload.get("definition"))
    except (ValueError, TypeError):
        raise StandardResponseExc(msg="策略配置无效，请检查名称、信号方向和条件选项")
    encoded = json.dumps(definition, ensure_ascii=False)
    strategy_id = payload.get("id")
    if strategy_id is None:
        row = await UserStrategyTable.aio_create(user_id=user_id, definition=encoded)
        return serialize(row)
    if not isinstance(strategy_id, str) or len(strategy_id) != 32:
        raise StandardResponseExc(msg="模型标识无效")
    version = payload.get("version")
    if type(version) is not int or version < 1:
        raise StandardResponseExc(msg="模型版本无效，请刷新")
    updated_at = int(time.time())
    count = await UserStrategyTable.update(
        definition=encoded, version=version + 1, update_ts=updated_at
    ).where(UserStrategyTable.id == strategy_id,
            UserStrategyTable.user_id == user_id,
            UserStrategyTable.version == version).aio_execute()
    if not count:
        raise StandardResponseExc(msg="模型不存在或已被修改，请刷新后重试")
    return {"id": strategy_id, "version": version + 1,
            "definition": definition, "update_ts": updated_at}
