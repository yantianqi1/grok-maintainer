# 上游 Key 控制台升级设计

## 目标

把现有管理员后台升级为中文紧凑界面，并补齐密钥运维需要的三个能力：

- 显示单独密钥的成功调用次数
- 支持按状态快速筛选
- 支持批量启用、批量禁用、批量删除

## 设计结论

### 数据层

- 在 `upstream_api_keys` 表增加 `success_count` 字段，默认值为 `0`
- `record_key_success()` 在更新时间的同时递增成功次数
- 列表查询支持过滤条件：
  - `all`
  - `enabled`
  - `disabled`
  - `error`
  - `unused`

### 路由层

- `GET /admin` 读取 `filter` 查询参数并回显当前筛选
- 新增 `POST /admin/keys/bulk-action`
- 批量操作提交：
  - `action=enable`
  - `action=disable`
  - `action=delete`
- 未选择密钥或提交非法操作时直接提示错误，不做静默兜底

### 界面层

- 控制台所有标题、说明、按钮文案统一改为中文
- 布局改为更紧凑的工具台样式：
  - 顶部摘要更扁平
  - 批量导入、筛选、批量操作放到同一工作区
  - 表格行高、按钮尺寸、边距整体收紧
- 列表增加复选框列和“成功次数”列

### 测试

- `tests/test_admin_store.py`
  - 验证成功次数递增
  - 验证筛选结果
  - 验证批量操作
- `tests/test_admin_views.py`
  - 验证后台页面显示成功次数与中文筛选项
  - 验证批量启用/禁用/删除路由

