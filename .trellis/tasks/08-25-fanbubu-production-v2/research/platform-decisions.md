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

QWeather 当前天气 API 接受 `经度,纬度`，无需先做逆地理编码；API Key 可放 `X-QW-Api-Key` 请求头，请求必须使用用户项目自己的 API Host。其当前按量档位为每月前 50,000 次免费、随后 950,000 次 0.0007 元/次，标准共享服务 QPM 3000。文档还提示 2027-01-01 起 API Key 鉴权会限制每日调用量，因此服务端必须缓存，后续可按量评估是否改 JWT 鉴权。

高德天气只接受 adcode；从小程序经纬度出发通常需要逆地理编码再查询天气。个人认证天气月免费额度 5,000 次、QPS 3，超额天气查询均价 30 元/万次。它适合作为低频国内备用源，不适合在本项目中承担每次请求主源。

结论：当前版本只接 QWeather，配合 last-good 缓存和 neutral 末级降级；高德留作后续按真实故障率决定的扩展项，Open-Meteo 退出生产默认链路；不因天气供应商单独购买 VPC/NAT。

参考：

- <https://docs.cloudbase.net/run/deploy/networking/egress>
- <https://dev.qweather.com/docs/api/weather/weather-now/>
- <https://dev.qweather.com/docs/configuration/authentication/>
- <https://dev.qweather.com/docs/finance/pricing/>
- <https://dev.qweather.com/en/docs/features/performance/>
- <https://lbs.amap.com/api/webservice/guide/api/weatherinfo>
- <https://lbs.amap.com/pages/base_service_price>
