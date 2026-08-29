# 外部依据与结论

## CloudBase 与微信身份

- CloudBase 官方说明：微信小程序通过 `wx.cloud.callContainer` 访问微信云托管时走特殊私有链路，后端可获得可信用户身份；正式链路无需在客户端保存 AppSecret。
  - https://docs.cloudbase.net/run/develop/access/mini
- 头像昵称是用户可选展示资料，微信官方组件使用 `chooseAvatar` 与 `input type=nickname`，与 OpenID 身份认证分离。
  - https://github.com/wechat-miniprogram/mp-user-avatar

## 推荐与营养

- MMR 通过相关性与新颖性的边际权衡降低列表冗余，适合作为候选后处理而非替代基础评分。
  - https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf
- 上下文 bandit 用于在已知偏好与探索之间取得长期收益；饭卜卜只采用受质量带约束的轻量探索，不在 MVP 阶段训练复杂在线模型。
  - https://arxiv.org/abs/1003.0146
- 《中国居民膳食指南（2022）》强调食物多样和合理搭配，可作为周级食材覆盖指标依据，但不支持把节气/体质包装为医疗结论。
  - https://www.cnsoc.org/bookpublica/0522202019.html

