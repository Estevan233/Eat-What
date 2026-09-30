# Jev 与轻量推荐调研
核验日期：2026-09-30。通过 web-access 浏览器读取公开页面；未调用付费 Jev API，未测量生产性能。

## 第一方模型证据
- https://docs.typesafe.ai/introduction ：输入 state + typed questions，输出 Choice、Score、Noul；Choice/Score 含 probabilities/confidence。原子问题独立评估，组合逻辑在代码。
- https://docs.typesafe.ai/models ：当前 jev-1.13.0；输入 $0.042/M tokens，输出免费；40 requests/s、100K tokens/s，限制可能调整。单请求 64K、state+最长问题 32K；仅文本。
- 同页明确英语效果最好，中文等 CJK 需要自测；不以客户请求训练不等于所有账号零留存。
- https://docs.typesafe.ai/patterns/composite-scoring ：分别评分后在代码归一化、加权；适合解释和调试，不等于官方已证明餐食推荐有效。
- https://docs.typesafe.ai/model-jaggedness/jev-1.13 ：官方 2026-09-17 更新局限：数字/计数/日期比较不可靠；大段无关上下文降质；易字面理解，受对抗文本影响；不用于生成文本。
- 模型精确算价/预算/曝光窗口/地理距离均不合适；这些交给代码。Noul 与 Choice 的概率不可直接互换，阈值需针对任务校验。
- 成本示例：每次总输入 5,000 tokens × 每天 1,000 次 × 30 天 × $0.042/M = $6.30/月，仅模型输入估算，不含重试、地图、云托管及其他模型。单次 token 必须包括所有问题。

## 社区目录（线索，不是性能证明）
https://logicrw.github.io/awesome-jev-projects/en/
页面显示 799 repos indexed（动态数值），按分类/路由/决策等展示；明确声明性能未经独立测试。
目录说明某些项目只包含可选适配器，不能把大仓库 star 数当成 Jev 实际采用率或质量证据。
可借鉴模式：语义判断与执行策略分离、只从已有选项选择、保留概率及回退；本轮未逐一审计其链接仓库，不声明社区集成均真实部署。

## WhatToOrder 实际观察
https://whattoorder.app/ （页面自动到 ?r=cheesecake-factory）
可见自然语言输入、快捷需求和预设菜单。点击公开 “something spicy” 按钮后，页面显示 “331 dishes sorted instantly”、54 个匹配结果分页，含 Spicy Jambalaya Arancini、Tex Mex Eggrolls 等。
上述是页面展示及一次交互观察；“instantly”不是实测延迟，未从服务端源码或调用证据核实具体模型，也未核验菜品现售状态、营养准确性及中国覆盖。
值得借鉴：先有有限真实候选，用一句需求重新排序；不要求先聊天。不复制全屏菜单、强制上传或健康功效话术。

## 地图证据（同日上轮已核验）
https://developers.weixin.qq.com/miniprogram/dev/component/map.html ：地图展示与位置服务搜索不同，地图数据体系衔接；商业行为存在授权收费要求。
https://developers.weixin.qq.com/miniprogram/dev/api/location/wx.chooseLocation.html ：需位置相关场景、后台开通和声明。
https://lbs.qq.com/faq/accountQuota/faqQuota ：个人额度与企业授权不同，当前个人暂不能购买配额；以账号和客服书面回复为准，不承诺个人免费商用。

## 结论与未验证项
模型优势假设是低价结构化语义评分，不是自动补全本地餐厅或保证不重复。先修候选/曝光/选集，再验证模型的增量收益。
国内 CloudBase 到 Jev 的延迟/稳定性、中文效果、真实 token、账号条款及数据传输合规均未验证；不得据此直接承诺上线收益。
