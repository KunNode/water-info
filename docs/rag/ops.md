# RAG 运维说明

## 1. 环境变量

AI 服务新增以下配置：

```env
EMBEDDING_API_KEY=
EMBEDDING_API_BASE=
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIM=1024
RAG_TOP_K=5
RAG_MIN_SCORE=0.25
RAG_CHUNK_SIZE=500
RAG_CHUNK_OVERLAP=80
```

建议：

- `EMBEDDING_API_BASE` 指向 OpenAI 兼容 embedding 服务。
- `EMBEDDING_MODEL` 与数据库中 `kb_document.embedding_model` 保持一致，切换模型后执行重建。
- `RAG_MIN_SCORE` 用于控制引用保守度，偏低会更容易召回，偏高会更容易漏掉证据。

## 2. 文档接入流程

1. 管理后台上传 `md / txt / pdf / docx`。
2. AI 服务创建 `kb_document` 与 `kb_ingest_job`。
3. 后台任务执行解析、分块、embedding、写入 `kb_chunk / kb_embedding`。
4. 文档状态从 `pending` / `processing` 进入 `ready` 或 `failed`。

## 3. 重建索引

适用场景：

- 切块策略调整
- embedding 模型调整
- 某批文档 ingest 失败后重试

操作方式：

- 后台页面点击“重建”
- 或调用 `POST /api/v1/kb/documents/{id}/reindex`

## 4. 故障排查

### 4.1 上传后一直是 `failed`

优先检查：

- `kb_ingest_job.error`
- embedding 服务是否可达
- PDF / DOCX 解析依赖是否已安装

### 4.2 能上传但搜不到

优先检查：

- 文档状态是否为 `ready`
- `chunk_count` 是否大于 0
- `embedding_model` 是否为空
- `/api/v1/kb/search` 调试结果是否仅剩关键词召回

### 4.3 切换 embedding 模型后结果异常

当前实现假设同一部署窗口内主要使用单一 embedding 模型。切换模型后建议：

1. 更新环境变量。
2. 对现有文档批量执行重建。
3. 用后台“检索调试”确认命中质量后再开放给业务使用。
