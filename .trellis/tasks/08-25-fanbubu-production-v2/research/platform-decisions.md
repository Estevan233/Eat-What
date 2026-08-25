# 外部平台决策记录（2026-08-25）

## 微信身份

用户提供的参考文章采用 `wx.login -> code2Session -> openid/session_key -> 自定义 token`，这个身份交换顺序仍可用于理解登录，但文章里的 `getUserInfo/scope.userInfo` 头像昵称方式不作为本项目实现依据。当前项目已经通过 CloudBase `callContainer` 的可信请求头取得 openid，不应为了头像昵称重新把 AppSecret 暴露或启用 code2session。

结论：openid/JWT 与头像昵称分离。登录先完成，资料由用户通过 nickname 输入和 chooseAvatar 主动填写，可跳过。

参考：

- <https://blog.csdn.net/baidu_33298752/article/details/130946848>
- 项目本地 CloudBase 身份技能与 `backend/app/api/v1/auth.py`

## CloudBase AI

官方文档要求小程序基础库至少 3.15.1、环境已初始化且目标模型已在控制台开启。小程序可用 `wx.cloud.extend.AI.createModel("cloudbase")` 调用具体模型，也可以用 `wx.cloud.extend.AI.bot.sendMessage` 调 Agent。

结论：MVP 先直接调用模型做结构化意图解析，不引入独立 Agent 对话页；实施前必须确认当前环境的 Token、模型组和模型可用。前端不放 API Key。

参考：<https://docs.cloudbase.net/ai/quickstart/miniprogram>

## 天气与公网出访

CloudBase 官方说明云托管默认可经平台出口访问第三方公网 API；关闭该出向能力才需要 VPC+NAT。当前 Open-Meteo 的 ConnectTimeout 说明特定外部路径不稳定，不等价于 Cloud Run 完全不能出公网。

QWeather 当前天气 API 接受 `经度,纬度`，无需先做逆地理编码；API Key 可放 `X-QW-Api-Key` 请求头，请求必须使用用户项目自己的 API Host。QWeather 文档还提示 2027-01-01 起 API Key 鉴权会有每日调用量限制，因此服务端必须缓存并保留备用源，后续可按量评估是否改 JWT 鉴权。

结论：QWeather 国内主源、Open-Meteo 备用、last-good 缓存和 neutral 末级降级；不购买 VPC/NAT。

参考：

- <https://docs.cloudbase.net/run/deploy/networking/egress>
- <https://dev.qweather.com/docs/api/weather/weather-now/>
- <https://dev.qweather.com/docs/configuration/authentication/>

