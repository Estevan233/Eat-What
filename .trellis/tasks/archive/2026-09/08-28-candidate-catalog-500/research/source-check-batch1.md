# 首批候选来源核验记录

核验时间：2026-08-31（Asia/Shanghai）
核验方式：通过用户已授权的浏览器页面读取正文，不使用搜索结果页作为 source_url。

## 主要来源

- URL：https://www.ihchina.cn/project_details/10278
- 页面标题：舌尖上的非遗
- 站点责任主体：主管中华人民共和国文化和旅游部；主办中国艺术研究院、中国非物质文化遗产保护中心。
- 页面正文明确列举或讨论的名称包括：北方饺子、南方元宵、西安羊肉泡馍、北京烤鸭、淮安豆腐、开封灌汤包、桂发祥十八街麻花、五芳斋粽子、南翔小笼、汉中面皮、宁夏手擀面、蓝田裤带面、四川甜水面、陕西臊子面、山西饸饹、武汉热干面、重庆小面、苏州头汤面、杭州片儿川、台湾眷村牛肉面、广州竹升面、新疆烤馕、香港虾籽捞面、兰州拉面、西安腊汁肉夹馍、蛋饺、条头糕、重阳糕、黄松糕、青团、红龟粿、糖瓜、茶泡等。

## 使用边界

该页面只证明菜名/地域/传统饮食语境，不证明实时商户库存、价格、配送能力、精确营养或医疗功效。批次脚本因此统一保持 review_status=draft、nature=unknown、seasonal_solar_terms=[all_season]；共享组合、份量和配送字段须取得菜单或人工复核证据后才可进入 source_verified/content_reviewed。

## 审核结果

首批 52 条已写入 backend/data/external_dining_seed.json，每条有稳定 catalog_key、anchor_food 和 68–92 的连续性评分；没有任何记录被自动批准。审核清单由 build_candidate_review_manifest.py 生成，当前总行数 109，线上导入器仍只接收 approved && is_active。

## 自动可达性检查

新增 `validate_external_dining_seed.py --check-sources` 只请求去重后的 URL 响应头，遇到站点拒绝 HEAD 时回退为 Range GET，不下载页面正文。2026-08-31 在 WSL 实测结果：GitHub 来源可达；中国非物质文化遗产网在该 WSL 网络链路出现 TLS `UNEXPECTED_EOF_WHILE_READING`，因此本次不能把“WSL 请求失败”记为来源失效。浏览器已能读取该页面正文，但正式 source_verified 仍需在部署/CI 网络中再次执行检查并由人工确认页面事实边界。
