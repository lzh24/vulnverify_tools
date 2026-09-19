from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_httpauth import HTTPBasicAuth
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import base64
from io import BytesIO

# Flask应用初始化
app = Flask(__name__)
auth = HTTPBasicAuth()

# Basic认证配置（本地独立 helper，密码与历史版本保持一致）
HASHED_PASSWORD = generate_password_hash('By#@4@l8IUif&xXO')  

@auth.verify_password
def verify_password(username, password):
    # 这里假设用户名固定为"admin"，实际使用时可以改为动态验证
    if username == 'admin' and check_password_hash(HASHED_PASSWORD, password):
        return username
    return None

# 日志配置
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

def take_screenshot(url, loading_strategy='none', sleep_time=0, user_agent=None, window_size='1920,1080'):
    """
    捕获网页截图的函数
    
    参数:
        url: 目标网页URL
        loading_strategy: 页面加载策略 (none, eager, normal)
        sleep_time: 页面加载后的等待时间(秒)
        user_agent: 自定义用户代理字符串
        window_size: 浏览器窗口大小 (宽x高)
    
    返回:
        Base64编码的截图数据或None
    """
    try:
        # 初始化Chrome选项
        options = Options()
        options.headless = True  # 无头模式
        options.page_load_strategy = loading_strategy  # 设置页面加载策略
        
        # 添加通用参数
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')  # 禁用沙盒模式
        options.add_argument('--disable-dev-shm-usage')  # 禁用共享内存
        options.add_argument(f'--window-size={window_size}')  # 设置窗口大小
        options.add_argument('--ignore-certificate-errors')  # 忽略证书错误
        
        # 设置用户代理
        if user_agent:
            options.add_argument(f'user-agent={user_agent}')
        else:
            default_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
            options.add_argument(f'user-agent={default_ua}')
        
        # 初始化WebDriver
        driver_path = r"/usr/local/bin/chromedriver"  # 请替换为您的ChromeDriver路径
        service = webdriver.ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)  # 设置页面加载超时时间
        
        # 访问目标URL
        app.logger.info(f"Loading URL: {url}")
        driver.get(url)
        
        # 等待页面加载
        app.logger.info(f"Sleeping for {sleep_time} seconds...")
        time.sleep(sleep_time)
        
        # 等待页面元素加载完成
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception as e:
            app.logger.warning(f"Page load timeout or error: {str(e)}")
        
        # 截图并转换为Base64
        screenshot = driver.get_screenshot_as_base64()
        app.logger.info("Screenshot captured successfully")
        
        # 释放资源
        driver.quit()
        return screenshot
    
    except Exception as e:
        app.logger.error(f"Screenshot error: {str(e)}", exc_info=True)
        if 'driver' in locals():
            driver.quit()
        return None

@app.route('/screenshot', methods=['POST'])
@auth.login_required
def screenshot_api():
    """
    截图API接口
    """
    try:
        # 获取原始请求体文本信息
        raw_request_data = request.data.decode('utf-8')
        app.logger.info(f"Received raw request data: {raw_request_data}")
        # 获取请求数据
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No input data provided'}), 400
        
        # 必填参数验证
        url = data.get('url')
        if not url:
            return jsonify({'error': 'Missing required parameter: url'}), 400
        
        # 可选参数处理
        loading_strategy = data.get('loadingStrategy', 'none')
        sleep_time = int(data.get('sleepTime', 0))
        user_agent = data.get('userAgent')
        window_size = data.get('windowSize', '1920,1080')
        
        # 忽略position参数
        if 'position' in data:
            app.logger.info("Position parameter received but not used")
        
        # 验证参数类型
        if not isinstance(sleep_time, int):
            return jsonify({'error': 'Invalid parameter type: sleepTime must be an integer'}), 400
        if loading_strategy not in ['none', 'eager', 'normal']:
            return jsonify({'error': 'Invalid loadingStrategy value'}), 400
        
        # 执行截图
        screenshot = take_screenshot(url, loading_strategy, sleep_time, user_agent, window_size)
        
        if screenshot:
            return jsonify({'screenshot': screenshot})
        else:
            return jsonify({'error': 'Failed to capture screenshot'}), 500
    
    except Exception as e:
        app.logger.error(f"API error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.logger.info("Starting screenshot service on port 8091")
    app.run(host='0.0.0.0', port=8091, debug=False)

