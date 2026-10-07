# 骑马钉小册子拼版

上传混合尺寸、含旋转页的 PDF，按骑马钉方式拼版：选择纸张、左/右装订、每帖 4/8/16 页与双面翻转方式，在线预览每张纸的正反面，并下载可直接送印的可打印 PDF。

## 功能

- **分帖拼版**：每帖 4 / 8 / 16 页；每帖独立补白至 4 的倍数，帖间不借页；折叠后页序与原稿一致
- **混合原稿**：支持各页尺寸不一、带 `/Rotate` 旋转的 PDF，原稿页面等比缩入版心，正反面对位
- **装订与双面**：左/右装订（右装订自动镜像）；按打印机「长边翻转 / 短边翻转」自动处理背面方向
- **文件校验**：加密（需口令）或损坏的 PDF 会报明具体原因，且不在服务器留下任何半成品
- **预览**：每张纸的正、反面均以图片预览，并标注左右格页码

## 技术栈

- 前端：React 18 + TypeScript + Vite（nginx 托管并反代 `/api`）
- 后端：FastAPI + PyMuPDF（拼版、渲染预览均在内存完成，不落盘）

## 一键启动（Docker）

```bash
docker compose up --build
```

依赖随镜像构建自动初始化，无需手动安装。

## 访问地址与端口

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| 网站（前端） | http://localhost:8080 | 页面入口， `/api` 由 nginx 代理到后端 |
| 后端 API | http://localhost:8000 （容器内） | 仅容器网络暴露；文档见 `/api/docs`（可经前端端口访问，如 http://localhost:8080/api/docs） |

## 本地开发（不用 Docker）

```bash
# 后端（Python 3.11+）
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# 前端（Node 20+），另开终端；Vite 已配置 /api 代理到 8000
cd frontend
npm install
npm run dev        # http://localhost:5173
```

## 测试

```bash
cd backend
python -m pytest tests/ -q
```

## 配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MAX_UPLOAD_MB` | `100` | 后端上传大小上限（MB）；nginx 侧为 `client_max_body_size 120m`，调大需同步修改 `frontend/nginx.conf` |
| `CORS_ORIGINS` | `http://localhost:5173` | 允许跨域的来源（逗号分隔），仅本地前后端分离开发需要 |
| `VITE_API_TARGET` | `http://localhost:8000` | 前端 dev server 的 `/api` 代理目标 |

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/documents` | 上传 PDF 并校验，返回页数与逐页尺寸/旋转；加密/损坏返回 422 及原因 |
| `POST` | `/api/documents/{id}/impose` | 按选项拼版，返回任务 ID、帖数、补白数与每张纸的页码排布 |
| `GET` | `/api/jobs/{id}/previews/{sheet}/{front\|back}` | 指定纸张正/反面的 PNG 预览 |
| `GET` | `/api/jobs/{id}/download` | 下载可打印 PDF |

上传的原稿与拼版结果仅保存在内存中，30 分钟后自动过期清理。
