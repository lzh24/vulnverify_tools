# Mac 本地开发环境配置指南

## 问题说明

在Mac上运行截图工具时，可能会遇到 `Unable to locate or obtain driver for chrome` 错误。这是因为代码中硬编码了Linux的ChromeDriver路径。

## 解决方案

### 方案 1: 使用 Homebrew 安装 Chrome 和 ChromeDriver（推荐）

```bash
# 1. 安装 Chrome（如果还未安装）
brew install --cask google-chrome

# 2. 安装 ChromeDriver
brew install chromedriver

# 3. 验证安装
chromedriver --version
which chromedriver

# 4. 如果遇到"无法打开chromedriver，因为无法验证开发者"的提示
xattr -d com.apple.quarantine $(which chromedriver)
```

ChromeDriver 默认安装路径：`/opt/homebrew/bin/chromedriver` (Apple Silicon) 或 `/usr/local/bin/chromedriver` (Intel)

### 方案 2: 使用 webdriver-manager 自动管理（已集成）

代码已经集成了 `webdriver-manager`，它会自动下载和管理ChromeDriver。无需手动安装。

### 方案 3: 手动下载安装

1. 访问 [ChromeDriver 下载页面](https://chromedriver.chromium.org/downloads)
2. 下载与您的 Chrome 版本匹配的 ChromeDriver
3. 解压并移动到系统路径：
   ```bash
   sudo mv chromedriver /usr/local/bin/
   sudo chmod +x /usr/local/bin/chromedriver
   ```

## 环境变量配置

在项目根目录的 `.env` 文件中，根据您的Mac环境配置：

```bash
# Mac Apple Silicon (M1/M2/M3)
CHROMEDRIVER_PATH=/opt/homebrew/bin/chromedriver
CHROMIUM_BINARY=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome

# Mac Intel
CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
CHROMIUM_BINARY=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

**注意**: 如果使用 webdriver-manager 自动管理，可以不设置这些变量。

## 验证配置

运行测试脚本验证配置：

```bash
# 测试基本功能
python -c "from selenium import webdriver; from selenium.webdriver.chrome.service import Service; driver = webdriver.Chrome(); driver.quit(); print('Success!')"
```

## 常见问题

### 1. 权限错误

```bash
# 错误: Permission denied
sudo chmod +x /usr/local/bin/chromedriver
xattr -d com.apple.quarantine /usr/local/bin/chromedriver
```

### 2. 版本不匹配

```bash
# 检查 Chrome 版本
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version

# 下载对应版本的 ChromeDriver
# https://chromedriver.chromium.org/downloads
```

### 3. M1/M2/M3 芯片兼容性

Apple Silicon Mac 需要使用 ARM64 版本的 ChromeDriver，Homebrew 会自动处理。

### 4. 使用 Rosetta 模式

如果遇到架构不兼容，可以在 Rosetta 模式下运行：

```bash
arch -x86_64 python main.py
```

## 推荐工作流程

### 开发环境（Mac）

1. 使用 Homebrew 安装 Chrome 和 ChromeDriver
2. 不设置环境变量，让代码自动检测
3. 如果自动检测失败，在 `.env` 中配置路径

### 生产环境（Docker）

使用 Docker 部署，无需配置：

```bash
docker-compose up -d --build
```

Docker 镜像已包含所有依赖。

## 测试截图功能

```bash
# 测试网页截图
curl -X POST http://localhost:8000/execute/screenshot/web_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "url": "https://example.com"
    }
  }' | jq -r '.data.screenshot' | base64 -d > test.png

# 查看截图
open test.png
```

## 相关资源

- [Selenium 文档](https://www.selenium.dev/documentation/)
- [ChromeDriver 下载](https://chromedriver.chromium.org/downloads)
- [Homebrew 官网](https://brew.sh/)
- [webdriver-manager 文档](https://github.com/SergeyPirogov/webdriver_manager)