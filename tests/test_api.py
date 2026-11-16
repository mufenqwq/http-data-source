import base64
import json
import os
import re
import unittest

import phonenumbers
from phonenumbers import NumberParseException

import app as server

USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,30}[a-zA-Z0-9]$")
EMAIL_RE = re.compile(r"^[\w.-]+@[\w.-]+\.[A-Za-z]{2,6}$")


class ApiTest(unittest.TestCase):
    def setUp(self):
        os.environ["BEARER_TOKEN"] = "test-token"
        os.environ["BASIC_USERNAME"] = "bkuser"
        os.environ["BASIC_PASSWORD"] = "bkuser"
        os.environ["USER_TOTAL"] = "121"
        os.environ.pop("BK_APP_CODE", None)
        os.environ.pop("BK_APP_SECRET", None)
        os.environ.pop("AUTH_DISABLED", None)
        self.client = server.app.test_client()

    def _get(self, path, **kwargs):
        headers = kwargs.pop("headers", {})
        headers.setdefault("Authorization", "Bearer test-token")
        return self.client.get(path, headers=headers, **kwargs)

    def test_healthz_and_index_do_not_require_auth(self):
        healthz = self.client.get("/healthz")
        index = self.client.get("/")
        self.assertEqual(healthz.status_code, 200)
        self.assertEqual(healthz.get_json()["status"], "ok")
        self.assertEqual(index.status_code, 200)
        self.assertEqual(index.get_json()["users_api"], "/apis/v1/users")
        self.assertEqual(index.get_json()["user_count"], 121)

    def test_users_require_auth(self):
        response = self.client.get("/apis/v1/users")
        self.assertEqual(response.status_code, 401)

        response = self.client.get("/apis/v1/users", headers={"Authorization": "Bearer wrong"})
        self.assertEqual(response.status_code, 401)

    def test_bearer_and_basic_auth(self):
        response = self._get("/apis/v1/users?page=1&page_size=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["results"][0]["username"], "sanzhang")

        basic = base64.b64encode(b"bkuser:bkuser").decode()
        response = self.client.get("/apis/v1/departments?page=1&page_size=1", headers={"Authorization": f"Basic {basic}"})
        self.assertEqual(response.status_code, 200)
        department = response.get_json()["results"][0]
        self.assertEqual(department["id"], "company")
        self.assertIsNone(department["parent"])

        wrong_basic = base64.b64encode(b"bkuser:wrong").decode()
        response = self.client.get("/apis/v1/users", headers={"Authorization": f"Basic {wrong_basic}"})
        self.assertEqual(response.status_code, 401)

    def test_gateway_auth_open_mode_and_exact_match(self):
        header = json.dumps({"bk_app_code": "bk-user", "bk_app_secret": "any-secret"})
        response = self.client.get("/apis/v1/users", headers={"X-Bkapi-Authorization": header})
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            "/apis/v1/users", headers={"X-Bkapi-Authorization": json.dumps({"bk_app_code": "bk-user"})}
        )
        self.assertEqual(response.status_code, 401)

        os.environ["BK_APP_CODE"] = "bk-user"
        os.environ["BK_APP_SECRET"] = "expected-secret"
        response = self.client.get("/apis/v1/users", headers={"X-Bkapi-Authorization": header})
        self.assertEqual(response.status_code, 401)
        matched = json.dumps({"bk_app_code": "bk-user", "bk_app_secret": "expected-secret"})
        response = self.client.get("/apis/v1/users", headers={"X-Bkapi-Authorization": matched})
        self.assertEqual(response.status_code, 200)

    def test_auth_can_be_disabled(self):
        os.environ["AUTH_DISABLED"] = "true"
        response = self.client.get("/apis/v1/users?page=1&page_size=1")
        self.assertEqual(response.status_code, 200)

    def test_pagination_contract(self):
        first = self._get("/apis/v1/users?page=1&page_size=100").get_json()
        second = self._get("/apis/v1/users?page=2&page_size=100").get_json()
        beyond = self._get("/apis/v1/users?page=3&page_size=100").get_json()

        self.assertEqual(first["count"], 121)
        self.assertEqual(len(first["results"]), 100)
        self.assertEqual(second["count"], 121)
        self.assertEqual(len(second["results"]), 21)
        self.assertEqual(beyond["results"], [])
        self.assertEqual(beyond["count"], 121)
        self.assertEqual(
            {item["id"] for item in first["results"]} & {item["id"] for item in second["results"]},
            set(),
        )

        default_page = self._get("/apis/v1/users").get_json()
        self.assertEqual(len(default_page["results"]), 100)
        self.assertEqual(self._get("/apis/v1/users?page=0").status_code, 400)
        self.assertEqual(self._get("/apis/v1/users?page_size=5001").status_code, 400)
        self.assertEqual(self._get("/apis/v1/users?page=abc").status_code, 400)

        # 用户管理配置里可以附带自定义查询参数，服务应忽略不认识的参数。
        extra = self._get("/apis/v1/users/?page=1&page_size=1&scope=company")
        self.assertEqual(extra.status_code, 200)
        self.assertEqual(extra.get_json()["results"][0]["id"], "100")

    def test_dataset_can_be_synced(self):
        os.environ["USER_TOTAL"] = "8"
        users = self._get("/apis/v1/users?page=1&page_size=100").get_json()["results"]
        departments = self._get("/apis/v1/departments?page=1&page_size=100").get_json()["results"]

        self.assertEqual([item["username"] for item in users[:3]], ["sanzhang", "sili", "wuwang"])
        self.assertEqual(users[1]["full_name"], "李四（已更新）")
        self.assertEqual(users[1]["email"], "lisi-updated@example.com")
        self.assertEqual(users[1]["phone"], "13800138002")
        self.assertEqual(users[3]["departments"], ["dept_a", "dept_b"])
        self.assertEqual(users[3]["leaders"], ["100", "101"])
        self.assertEqual(users[4]["email"], "")
        self.assertEqual(users[4]["phone"], "")
        self.assertEqual(users[5]["username"], "sunba")
        self.assertEqual(users[5]["full_name"], "孙八")
        self.assertEqual(users[5]["departments"], ["center_ba"])
        self.assertEqual(users[5]["leaders"], ["101"])
        self.assertEqual(users[6]["username"], "zhoujiu")
        self.assertEqual(users[6]["full_name"], "周九")
        self.assertEqual(users[6]["departments"], ["center_ab"])
        self.assertEqual(users[6]["leaders"], ["100"])

        department_ids = {item["id"] for item in departments}
        user_ids = {item["id"] for item in users}
        self.assertEqual(len(user_ids), len(users))
        for department in departments:
            self.assertIn("parent", department)
            if department["parent"] is not None:
                self.assertIn(department["parent"], department_ids)

        for user in users:
            self.assertRegex(user["username"], USERNAME_RE)
            self.assertTrue(user["full_name"])
            self.assertNotIn(user["id"], user["leaders"])
            if user["email"]:
                self.assertRegex(user["email"], EMAIL_RE)
            if user["phone"]:
                self.assertEqual(len(user["phone"]), 11)
                self.assertNotIn("+", user["phone_country_code"])
                try:
                    phonenumbers.parse(user["phone"], "CN")
                except NumberParseException as exc:
                    self.fail(f"{user['username']} phone {user['phone']} cannot be parsed: {exc}")
            for leader in user["leaders"]:
                self.assertIn(leader, user_ids)
            for department_id in user["departments"]:
                self.assertIn(department_id, department_ids)
            self.assertIsInstance(user["extras"], dict)
            self.assertTrue(all(isinstance(value, str) for value in user["extras"].values()))

    def test_unsupported_method_and_unknown_path(self):
        response = self.client.post("/apis/v1/users", headers={"Authorization": "Bearer test-token"})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.get("/missing").status_code, 404)


if __name__ == "__main__":
    unittest.main()
