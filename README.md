# Smart Launcher 6.6 build 021：拼音搜索增强版

这是基于已清理版本制作的 Smart Launcher 6.6 build 021 修改版，增强了桌面搜索和应用网格搜索。

## 搜索能力

对“微信”这类中文应用名，以下输入都可以命中：

- 首字母：`wx`
- 全拼：`weixin`
- 未完整输入的全拼前缀：`w`、`we`、`wei`、`weix`、`weixi`
- 从后一个汉字开始：`xin`

支持多音字、大小写和空格；原有中文、英文搜索仍由 Smart Launcher 自带匹配器处理。

## 文件

- `release/Smart-Launcher-6.6-021-cleaned-pinyin-search.apk`：可安装 APK
- `source/`：离线拼音匹配、DEX 补丁、构建和验证源码
- `拼音搜索增强版说明.md`：安装与安全说明
- `build-result.json`、`verification-result.json`：构建和静态校验结果

## 安全与兼容性

- 未新增 Android 权限。
- 新增代码不联网、不动态加载代码、不创建后台线程。
- 只改动桌面搜索和应用网格搜索两个调用点。
- APK 使用与之前清理版相同的本地签名，可覆盖同一签名的旧版；不能覆盖官方签名版本。

## 校验

APK SHA-256：`20296dca705e6c1a0f9a15732a589fc7a2f33e26f3dc8becdcac6eb844722eee`

构建通过 79 项匹配断言、80,000 次并发匹配压力测试，以及 ZIP/DEX/签名/对齐检查。尚未在实体手机上启动测试。

