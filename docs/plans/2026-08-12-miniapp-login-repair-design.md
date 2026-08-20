# 微信小程序登录修复设计

## 目标

修复微信开发者工具中游客登录和微信一键登录均无法发出请求的问题，并让登录失败原因在页面与调试器中可见。开发阶段继续使用 Windows 微信开发者工具访问 WSL 中的 FastAPI；本轮不迁移云托管。

## 已确认根因

- `api/request.ts` 为规避循环依赖而动态导入 Pinia store，但 uni-app 的 mp-weixin 产物把该表达式编译成了 `await "../stores/user.js"`，导致请求在 `uni.request` 之前中断。
- 登录页空 `catch` 吞掉异常，因此模拟器只有“按钮无反应”的表象。
- 后端游客登录接口可从 Windows 直连成功；微信登录还依赖本地 `.env` 中与当前小程序匹配的 AppID/AppSecret。
- DCloud 统计上报失败与认证无关，但会污染控制台。

## 设计

新增无框架依赖的 `auth/storage.ts`，统一读取、写入和清理认证持久化数据。请求层只从该模块读取 token，在 401 时清理持久化认证并跳转登录页；Pinia store 继续维护页面响应式状态，但通过同一模块持久化，不再被请求层导入。这样依赖方向固定为 `store -> api -> request -> auth storage`，不会形成环。

登录页捕获错误后记录结构化错误并展示可读提示。请求层继续负责 HTTP 错误 toast；发生在请求之前的 `wx.login` 或运行时错误由登录页兜底。用共享 loading 锁防止连续点击重复登录。

微信小程序平台关闭 uniStatistics，避免无关统计请求遮住业务错误。真实 AppSecret 只写入 WSL 的 `backend/.env`，不进入前端、不进入 Git。

## 验收

- 单元测试证明请求层在没有 Pinia active instance 时仍会调用 `uni.request`，并携带 storage 中的 token。
- 单元测试覆盖认证信息持久化和清理。
- `npm run test`、`type-check`、`lint:check`、`build:mp-weixin` 通过。
- 编译产物不再包含 `await "../stores/user.js"`，且包含正确 AppID、`app.json` 和禁用统计配置。
- Windows 能访问后端健康检查；游客登录直连成功；真实微信临时 code 只能由开发者工具生成，因此最终一键登录需在微信开发者工具中完成交互验收。

## 预览边界

模拟器可以通过 `http://localhost:8000` 联调 WSL。扫码预览运行在手机中，手机的 `localhost` 指向手机自己，因此在后端部署为 HTTPS/云托管前只能保证页面包可预览，不能保证登录和推荐联网成功。本轮不会把这个平台限制伪装成代码已经解决。
