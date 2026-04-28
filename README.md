# Amazon Product Data Scraper

一个基于 Selenium 和 BeautifulSoup 的 Amazon 产品数据刮削器，支持抓取产品信息、视频和详细描述。

## 功能特性

- 📦 批量抓取 Amazon 产品数据（支持 ASIN 列表）
- 🎥 自动提取产品视频和描述
- 📊 导出为 CSV 和 JSON 格式
- 🔐 支持 Cookies 登录状态保存
- 🎭 模拟人类行为（随机滚动、延迟）
- 🛡️ 反检测机制（隐藏 webdriver 标识）
- 📝 详细的日志记录

## 环境要求

- Python 3.7+
- Google Chrome 浏览器
- ChromeDriver（自动安装）

## 安装

```bash
# 克隆仓库
git clone https://github.com/guaiguaizyh/AMZ-Math-Analysis.git
cd amazon-scraper-python-Eva

# 安装依赖
pip install -r requirement.txt
```

## 使用方法

### 1. 准备 ASIN 列表

编辑 `asins.txt` 文件，每行一个 ASIN：

```
B0C6TKJWF3
B07T6HZW9S
B0D7Q1R7KK
...
```

### 2. 配置 Cookies（可选）

如果你需要登录状态：

1. 手动登录 Amazon
2. 导出 Cookies 并保存为 `cookies.json`
3. 运行时会自动加载已保存的 Cookies

### 3. 运行刮削器

```bash
# 默认模式（带浏览器窗口）
python amazon_scraper_1.0.0.py

# 无头模式（不显示浏览器窗口）
python amazon_scraper_1.0.0.py --headless
```

### 4. 查看结果

抓取结果会保存到：
- `output.csv` - CSV 格式
- `output.json` - JSON 格式
- `scraper_v2.log` - 详细日志

## 文件说明

```
├── amazon_scraper_1.0.0.py  # 主程序
├── asins.txt                # ASIN 产品列表
├── cookies.json             # Cookies 文件（自动生成）
├── output.csv               # CSV 输出（自动生成）
├── output.json              # JSON 输出（自动生成）
├── scraper_v2.log           # 日志文件（自动生成）
├── requirement.txt          # 依赖列表
├── run_asins.bat            # Windows 批处理脚本
├── .gitignore               # Git 忽略文件
└── .travis.yml              # CI 配置
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--headless` | 无头模式运行 | False |
| `--window-size` | 窗口大小 | 1920,1080 |
| `--page-load-timeout` | 页面加载超时（秒） | 25 |

## 示例

```bash
# 基本使用
python amazon_scraper_1.0.0.py

# 无头模式
python amazon_scraper_1.0.0.py --headless

# 自定义窗口大小
python amazon_scraper_1.0.0.py --window-size 2560,1440
```

## 注意事项

1. 遵守 Amazon 的服务条款和 robots.txt
2. 建议设置合理的抓取间隔，避免被封禁
3. 确保网络连接稳定
4. 如遇问题，检查 `scraper_v2.log` 日志文件

## 许可证

本项目仅供学习和研究使用。

## 作者

guaiguaizyh

## 更新日志

- v1.0.0 - 初始版本，支持基础产品抓取
