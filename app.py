# -*- coding: utf-8 -*-
"""供 bk-user 通用 HTTP 数据源联调的模拟服务。

协议与 bk-user 插件一致：GET 分页，响应体只有 count 和 results。
用户 extras 的值必须是字符串，插件会把 extras 合并进 properties。
超出总数的页码返回空 results，count 仍然是总数。
"""

import base64
import binascii
import hmac
import json
import logging
import os
from typing import Any

from flask import Flask, jsonify, request

logger = logging.getLogger("http_data_source")

MIN_USER_TOTAL = 3
MAX_USER_TOTAL = 10000
MAX_PAGE_SIZE = 5000

# 张三、王五和前三个部门与协议示例一致，连通性测试拿到的第一条仍是张三。李四的资料已改成更新后的值。
PROTOCOL_USERS = [
    {
        "id": "100",
        "username": "sanzhang",
        "full_name": "张三",
        "email": "1234567891@qq.com",
        "phone": "12345678901",
        "phone_country_code": "86",
        "extras": {"gender": "male"},
        "leaders": [],
        "departments": ["company"],
    },
    {
        "id": "101",
        "username": "sili",
        "full_name": "李四（已更新）",
        "email": "lisi-updated@example.com",
        "phone": "13800138002",
        "phone_country_code": "86",
        "extras": {"gender": "female"},
        "leaders": ["100"],
        "departments": ["dept_a"],
    },
    {
        "id": "102",
        "username": "wuwang",
        "full_name": "王五",
        "email": "1234567893@qq.com",
        "phone": "12345678903",
        "phone_country_code": "86",
        "extras": {"gender": "male"},
        "leaders": ["100", "101"],
        "departments": ["center_aa"],
    },
]

# 协议示例之外的固定场景：多个部门、多个上级、联系方式留空。
ZHAOLIU = {
    "id": "103",
    "username": "zhaoliu",
    "full_name": "赵六",
    "email": "zhaoliu@example.com",
    "phone": "13800138000",
    "phone_country_code": "86",
    "extras": {"gender": "male"},
    "leaders": ["100", "101"],
    "departments": ["dept_a", "dept_b"],
}
QIANQI = {
    "id": "104",
    "username": "qianqi",
    "full_name": "钱七",
    "email": "",
    "phone": "",
    "phone_country_code": "",
    "extras": {"gender": "female"},
    "leaders": [],
    "departments": ["dept_b"],
}
SUNBA = {
    "id": "105",
    "username": "sunba",
    "full_name": "孙八",
    "email": "sunba@example.com",
    "phone": "13800138008",
    "phone_country_code": "86",
    "extras": {"gender": "male"},
    "leaders": ["101"],
    "departments": ["center_ba"],
}
ZHOUJIU = {
    "id": "106",
    "username": "zhoujiu",
    "full_name": "周九",
    "email": "zhoujiu@example.com",
    "phone": "13800138009",
    "phone_country_code": "86",
    "extras": {"gender": "female"},
    "leaders": ["100"],
    "departments": ["center_ab"],
}

DEPARTMENTS = [
    {"id": "company", "name": "总公司", "parent": None, "extras": {"region": "CN"}},
    {"id": "dept_a", "name": "部门A", "parent": "company", "extras": {"region": "CN"}},
    {"id": "center_aa", "name": "中心AA", "parent": "dept_a", "extras": {"region": "US"}},
    {"id": "dept_b", "name": "部门B", "parent": "company", "extras": {"region": "CN"}},
    {"id": "center_ab", "name": "中心AB", "parent": "dept_a", "extras": {"region": "CN"}},
    {"id": "center_ba", "name": "中心BA", "parent": "dept_b", "extras": {"region": "US"}},
]

app = Flask(__name__)
app.json.ensure_ascii = False
app.url_map.strict_slashes = False


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _same(left: str, right: str) -> bool:
    left_bytes = left.encode("utf-8")
    right_bytes = right.encode("utf-8")
    if len(left_bytes) != len(right_bytes):
        return False
    return hmac.compare_digest(left_bytes, right_bytes)


def user_total() -> int:
    raw = os.getenv("USER_TOTAL", "121").strip()
    try:
        total = int(raw)
    except ValueError:
        logger.warning("USER_TOTAL=%s is invalid, fallback to 121", raw)
        total = 121
    return min(max(total, MIN_USER_TOTAL), MAX_USER_TOTAL)


def build_departments() -> list[dict[str, Any]]:
    return DEPARTMENTS


def build_users() -> list[dict[str, Any]]:
    total = user_total()
    users = list(PROTOCOL_USERS)
    if total >= 4:
        users.append(ZHAOLIU)
    if total >= 5:
        users.append(QIANQI)
    if total >= 6:
        users.append(SUNBA)
    if total >= 7:
        users.append(ZHOUJIU)

    department_ids = [item["id"] for item in DEPARTMENTS]
    # 105、106 分别留给孙八和周九，自动补齐的用户从 107 开始。
    serial = 107
    while len(users) < total:
        suffix = f"{serial:04d}"
        users.append(
            {
                "id": str(serial),
                "username": f"user{suffix}",
                "full_name": f"测试用户{suffix}",
                "email": f"user{suffix}@example.com",
                "phone": str(13800130000 + serial - 105),
                "phone_country_code": "86",
                "extras": {"gender": "male" if serial % 2 == 0 else "female"},
                "leaders": ["100"],
                "departments": [department_ids[(serial - 105) % len(department_ids)]],
            }
        )
        serial += 1
    return users


def _unauthorized(reason: str):
    logger.info("reject %s %s: %s", request.method, request.path, reason)
    return jsonify({"error": reason}), 401


def _check_basic(encoded: str):
    expected_username = os.getenv("BASIC_USERNAME", "bkuser")
    expected_password = os.getenv("BASIC_PASSWORD", "bkuser")
    if not expected_username or not expected_password:
        return _unauthorized("Basic Auth 未启用")

    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return _unauthorized("Basic Auth 无法解析")

    username, separator, password = decoded.partition(":")
    if not separator:
        return _unauthorized("Basic Auth 无法解析")
    if _same(username, expected_username) and _same(password, expected_password):
        return None
    return _unauthorized("Basic Auth 不正确")


def _check_gateway(raw_header: str):
    try:
        payload = json.loads(raw_header)
    except json.JSONDecodeError:
        return _unauthorized("蓝鲸网关认证信息不是合法 JSON")
    if not isinstance(payload, dict):
        return _unauthorized("蓝鲸网关认证信息格式不正确")

    app_code = str(payload.get("bk_app_code") or "")
    app_secret = str(payload.get("bk_app_secret") or "")
    if not app_code or not app_secret:
        return _unauthorized("蓝鲸网关认证信息缺少 bk_app_code 或 bk_app_secret")

    # 未同时配置时期望测试环境直接拿 bk-user 自己的应用凭证来调，不在这里写死密钥。
    expected_code = os.getenv("BK_APP_CODE", "").strip()
    expected_secret = os.getenv("BK_APP_SECRET", "").strip()
    if not expected_code or not expected_secret:
        return None
    if _same(app_code, expected_code) and _same(app_secret, expected_secret):
        return None
    return _unauthorized("蓝鲸网关认证信息不正确")


def authorize():
    if _env_flag("AUTH_DISABLED"):
        return None

    header = request.headers.get("Authorization", "")
    scheme, _, credential = header.partition(" ")
    scheme = scheme.lower()
    if scheme == "bearer":
        expected = os.getenv("BEARER_TOKEN", "test-token")
        if expected and _same(credential.strip(), expected):
            return None
        return _unauthorized("Bearer Token 不正确")
    if scheme == "basic":
        return _check_basic(credential.strip())

    gateway_header = request.headers.get("X-Bkapi-Authorization", "")
    if gateway_header:
        return _check_gateway(gateway_header)
    return _unauthorized("缺少认证信息")


def parse_pagination():
    raw_page = request.args.get("page", "1")
    raw_page_size = request.args.get("page_size", "100")
    try:
        page = int(raw_page)
        page_size = int(raw_page_size)
    except ValueError:
        return None, None, (jsonify({"error": "page 和 page_size 必须是整数"}), 400)
    if page < 1 or page_size < 1 or page_size > MAX_PAGE_SIZE:
        return None, None, (jsonify({"error": "page 从 1 开始，page_size 取值范围为 1 到 5000"}), 400)
    return page, page_size, None


def paginate(items: list[dict[str, Any]], page: int, page_size: int) -> dict[str, Any]:
    start = (page - 1) * page_size
    return {"count": len(items), "results": items[start : start + page_size]}


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.get("/")
def index():
    return jsonify(
        {
            "service": "bk-user-http-data-source",
            "healthz": "/healthz",
            "users_api": "/apis/v1/users",
            "departments_api": "/apis/v1/departments",
            "user_count": len(build_users()),
            "department_count": len(build_departments()),
            "auth_methods": ["bearer_token", "basic_auth", "bk_apigateway"],
        }
    )


@app.get("/apis/v1/users")
def list_users():
    denied = authorize()
    if denied is not None:
        return denied

    page, page_size, error = parse_pagination()
    if error is not None:
        return error

    payload = paginate(build_users(), page, page_size)
    logger.info(
        "users page=%s page_size=%s returned=%s total=%s",
        page,
        page_size,
        len(payload["results"]),
        payload["count"],
    )
    return jsonify(payload)


@app.get("/apis/v1/departments")
def list_departments():
    denied = authorize()
    if denied is not None:
        return denied

    page, page_size, error = parse_pagination()
    if error is not None:
        return error

    payload = paginate(build_departments(), page, page_size)
    logger.info(
        "departments page=%s page_size=%s returned=%s total=%s",
        page,
        page_size,
        len(payload["results"]),
        payload["count"],
    )
    return jsonify(payload)


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "method not allowed"}), 405


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
