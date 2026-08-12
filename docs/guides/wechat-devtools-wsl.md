# Windows 微信开发者工具 + WSL 调试与预览

本项目的唯一开发仓库是：

```text
/root/miniapp-trellis
```

Windows 下看到的 `\\wsl.localhost\Ubuntu-22.04\root\miniapp-trellis` 只是同一份 WSL 文件的访问入口，不是第二份代码。GitHub 是远端备份/协作仓库，也不是当前编辑目录。

这套前端是 **uni-app 源码**。微信开发者工具应导入编译产物中包含 `app.json` 的目录，不能直接导入仓库根目录、`miniapp` 或 `miniapp/src`。

## 1. 两条运行链路不要混用

### 本地 H5 联调

```text
浏览器 http://localhost:5173
  -> 本地 FastAPI http://localhost:8000
  -> 本地数据库
```

这条链路用于快速查看页面和调接口。

### 微信模拟器、预览和真机调试

```text
微信小程序
  -> wx.cloud.callContainer
  -> CloudBase 云托管服务 eat-what-api
  -> CloudBase MySQL
```

微信链路不再请求 `localhost:8000`。手机里的 `localhost` 是手机自己，不是 Windows，也不是 WSL；让真机访问它，只会稳定收获 `ERR_CONNECTION_REFUSED / errCode -102`。

使用 `callContainer` 后，小程序访问同一云开发环境内的云托管服务，MVP 通常不需要额外购买 VPS，也不需要为 API 单独准备 request 合法域名。

## 2. 编译微信小程序

在 WSL 的 VS Code 终端执行：

```bash
cd /root/miniapp-trellis/miniapp
npm install
npm run dev:mp-weixin
```

开发构建目录：

```text
\\wsl.localhost\Ubuntu-22.04\root\miniapp-trellis\miniapp\dist\dev\mp-weixin
```

发布构建使用：

```bash
cd /root/miniapp-trellis/miniapp
npm run build:mp-weixin
```

发布构建目录：

```text
\\wsl.localhost\Ubuntu-22.04\root\miniapp-trellis\miniapp\dist\build\mp-weixin
```

编译后先检查：

```bash
test -f dist/dev/mp-weixin/app.json && echo "app.json OK"
grep '"appid"' dist/dev/mp-weixin/project.config.json
```

不要直接修改 `dist`，它会在下一次 uni-app 编译时被覆盖。源码只改 `miniapp/src`。

## 3. 微信开发者工具正确导入

1. 打开 Windows 版微信开发者工具，选择“导入项目”，不要新建 QuickStart 模板。
2. 项目目录选择 `dist/dev/mp-weixin` 或 `dist/build/mp-weixin` 的完整 UNC 路径。
3. AppID 确认是 `wx59c5620b7a894f8e`。
4. 项目类型选择“小程序”，点击“编译”。
5. 云开发环境确认是 `cloud1-d8gz4jm8vb964a1c9`。

如果报 `app.json is not found in the project root directory`，导入层级错了。`app.json` 必须直接位于所选项目目录根部。

## 4. 云端配置必须一致

固定配置：

| 项目 | 值 |
|---|---|
| AppID | `wx59c5620b7a894f8e` |
| 云开发环境 ID | `cloud1-d8gz4jm8vb964a1c9` |
| 云托管服务名 | `eat-what-api` |
| 容器端口 | `8080` |

前端通过 `wx.cloud.init` 初始化该环境，并通过 `wx.cloud.callContainer` 访问服务。服务名或环境 ID 任意一个写错，结果都不会因为你多点几次“编译”而突然良心发现。

登录链路：

- 微信一键登录调用 `/api/v1/auth/cloud-login`；
- FastAPI 只信任 CloudBase 注入的微信身份请求头；
- 正常云托管路径不需要在前端保存或发送 AppSecret；
- 游客登录仍调用同一云托管服务。

## 5. 建议调试顺序

1. CloudBase 控制台确认 `eat-what-api` 最新版本部署成功且实例可启动。
2. 查看服务日志，确认数据库迁移、菜品和菜谱种子初始化成功。
3. 在开发者工具中清除缓存并重新编译。
4. 先测“游客登录”，再测“微信一键登录”。
5. Console 中确认没有 `localhost:8000` 请求。
6. 依次验证档案、今日三餐盘推荐、替换单项、菜谱详情、收藏、确认整套餐、历史记录。
7. 最后再做“预览”扫码和“真机调试”。

调试器中重点保留错误对象里的 `requestId`。它能与云托管日志对应，比截图一整屏红字更容易定位问题。

## 6. 编译、预览、真机调试和上传的区别

- **编译**：在开发者工具模拟器运行。
- **预览**：上传临时代码并生成二维码，手机扫码体验。
- **真机调试**：手机运行，同时与开发者工具连接查看日志。
- **上传**：上传一个可配置为体验版、随后提交审核的版本。

四者都需要云托管后端可用。前端能显示登录页，只能证明静态资源加载了，不能证明登录 API 已经活着。

## 7. 常见错误对照

| 现象 | 根因 | 处理 |
|---|---|---|
| `app.json is not found` | 导入了仓库、`miniapp` 或 `src` | 重新导入 `dist/dev/mp-weixin` |
| `SERVICE_CONFIG_ERROR` | 环境 ID、服务名、端口或云托管版本不一致 | 对照固定配置并查看云托管版本日志 |
| `errCode -102` / `ERR_CONNECTION_REFUSED` | 仍在请求 `localhost`，或云服务未启动 | 搜索构建产物中的 `localhost:8000`；检查云服务 |
| Network 显示旧的 `/auth/wx-login` + localhost | 开发者工具仍缓存旧产物 | 停止旧监听，重新构建，清缓存并重新导入 |
| 游客和微信登录都失败 | 更可能是容器、数据库或服务路由问题 | 先查 `/health` 和云托管日志，不要先怀疑微信授权 |
| 仅微信登录失败 | CloudBase 身份请求头或 AppID 配置问题 | 检查环境归属、AppID 和 `/auth/cloud-login` 日志 |
| 5xx | 容器启动、迁移、种子数据或数据库连接失败 | 查看首个异常和同一 `requestId` |
| 模拟器正常、手机失败 | 使用了旧构建，或预览版本未连接同一云环境 | 用发布构建重新预览并核对环境 ID |
| 点击“我的”无响应 | 旧包对 tabBar 页面使用了 `navigateTo` | 清缓存并使用包含 `switchTab` 修复的新构建 |

## 8. 发布前最短检查

```bash
cd /root/miniapp-trellis/miniapp
npm run lint
npm run type-check
npm test -- --run
npm run build:h5
npm run build:mp-weixin
test -f dist/build/mp-weixin/app.json
! grep -R "localhost:8000" dist/build/mp-weixin
```

然后导入 `dist/build/mp-weixin`，恢复正常安全校验，完成模拟器、预览二维码和真机三轮验收。

## 9. 官方参考

- [CloudBase 云托管：小程序访问服务](https://docs.cloudbase.net/run/develop/access/mini)
- [CloudBase 云托管：从源代码部署](https://docs.cloudbase.net/run/deploy/deploy/deploying-source-code)
- [uni-app CLI 运行与发行](https://uniapp.dcloud.net.cn/worktile/CLI.html)
