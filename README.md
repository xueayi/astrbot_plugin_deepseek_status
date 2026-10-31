# DeepSeek 官方状态推送

AstrBot 插件，从 [DeepSeek 官方状态页](https://status.deepseek.com/) 当前使用的 FlashDuty 数据接口读取状态。首次启动向配置的群发送当前状态，此后每 60 秒检查一次事件新增、更新与恢复，并在变化时推送。

部署到 AstrBot 的 `data/plugins/astrbot_plugin_deepseek_status`，在插件配置中填写目标会话，格式为 `平台ID:GroupMessage:群号`。`/dsstatus status` 可手动查询。状态记录在 AstrBot 插件数据目录，重启不会重复推送首次摘要。
