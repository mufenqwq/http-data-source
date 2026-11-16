# 用户管理 HTTP 数据源测试服务

给 bk-user 通用 HTTP 数据源做联调。服务按插件协议提供用户、部门两个分页接口，数据固定，重复同步结果不变。

这是一个独立应用，放到自己的 Git 仓库后部署。不要和 bk-user 的代码混在同一个提交里。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/apis/v1/users` | 用户 |
| GET | `/apis/v1/departments` | 部门 |
| GET | `/healthz` | 健康检查，不鉴权 |
| GET | `/` | 服务说明，不鉴权 |

查询参数：

- `page`：页码，从 1 开始，默认 1
- `page_size`：每页数量，默认 100，最大 5000
- 其他查询参数会被忽略。用户管理里配置的自定义查询参数不会导致请求失败

超出总数时 `results` 为空数组，`count` 仍是总数。张三和王五，以及前 3 个部门，仍与插件协议文档中的示例一致。默认一共 120 个用户、6 个部门，`page_size=100` 时用户会拉两页。

固定场景：

- 李四 `sili`：姓名改为「李四（已更新）」，邮箱改为 `lisi-updated@example.com`，手机号改为 `13800138002`，用来验证同步更新
- 赵六 `zhaoliu`：两个部门、两个直接上级
- 钱七 `qianqi`：邮箱和手机号为空
- 孙八 `sunba`：新增用户，部门是中心 BA，直接上级是李四

`USER_TOTAL` 最小 3、最大 10000。设为 3 时只有协议示例里的 3 个用户；设为 4 时增加赵六，设为 5 时再增加钱七，设为 6 及以上时再增加孙八，其余名额用 `user0106` 这种测试用户补齐。

## 鉴权

三种方式都可以，凭据来自环境变量。默认值：

| 方式 | 环境变量 | 默认值 |
| --- | --- | --- |
| Bearer Token | `BEARER_TOKEN` | `test-token` |
| Basic Auth | `BASIC_USERNAME` / `BASIC_PASSWORD` | `bkuser` / `bkuser` |
| 蓝鲸网关 | `BK_APP_CODE` / `BK_APP_SECRET` | 不配置 |

网关的两个变量都配置时，请求头里的 `bk_app_code`、`bk_app_secret` 必须一致。都留空时，只要 `X-Bkapi-Authorization` 是带非空应用编码和密钥的 JSON 就放行。

`AUTH_DISABLED=true` 可以关掉鉴权，只适合临时排障。

直接连这个应用时，用 Bearer Token 或 Basic Auth。用户管理里的「蓝鲸网关」认证会去请求网关地址，而不是这里的服务地址，需要先把本应用注册成网关后端。

## 在用户管理里填写

服务地址不能带路径，也不能以 `/` 结尾。

- 服务地址：部署后的应用根地址，例如 `https://stag-dot-bk-user-http-ds.example.com`
- 用户 API 路径：`/apis/v1/users`
- 部门 API 路径：`/apis/v1/departments`
- 认证方式：Bearer Token，口令 `test-token`

租户上如果有必填且没有默认值的自定义字段，同步会失败。这个服务的用户额外字段只有 `gender`。

## 本地运行

```bash
uv run --with flask python app.py
curl -H 'Authorization: Bearer test-token' 'http://127.0.0.1:5000/apis/v1/users?page=1&page_size=1'
```

检查：

```bash
uv run --with flask --with phonenumbers python -m unittest tests.test_api
```

## 部署到蓝鲸 PaaS

仓库根目录保持现在的结构：`app_desc.yaml`、`Dockerfile`、`requirements.txt`。

源码管理页面按下面填写：

- 代码源：Git 代码库
- 构建方式：Dockerfile
- 源代码地址：本仓库地址
- 构建目录：留空，使用仓库根目录
- Dockerfile 路径：留空，使用根目录的 `Dockerfile`

开发者中心的模块名如果不是 `default`，把 `app_desc.yaml` 里的 `modules.name` 改成实际模块名。`app.bkAppCode` 只在 S-mart 打包时生效，普通应用以页面上创建的应用 ID 为准。

镜像基于腾讯云镜像加速上的 `python:3.11-slim-bookworm`。依赖从 `mirrors.tencent.com` 安装。

进程监听 `PORT`，默认 5000，存活探针也访问 `5000/healthz`。平台如果把 Web 端口分配成别的值，同时改 `start.sh` 使用的端口和 `app_desc.yaml` 里的探针端口。

本地构建：

```bash
docker build -t bk-user-http-ds .
docker run --rm -p 5000:5000 bk-user-http-ds
```
