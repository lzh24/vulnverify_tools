from typing import Optional
from pydantic_settings import BaseSettings


class ToolConfig(BaseSettings):
    tool_token: str
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    web_concurrency: int = 2
    enable_request_logging: bool = False
    screenshot_max_concurrency: int = 2
    screenshot_executor_workers: int = 2
    screenshot_page_load_timeout: int = 20
    screenshot_element_wait_timeout: int = 10
    screenshot_request_timeout: int = 15
    screenshot_max_sleep_time: int = 3
    screenshot_upload_enabled: bool = True
    screenshot_return_base64_by_default: bool = False
    terminal_hub_return_base64_by_default: bool = False

    # Screenshot Tool Settings
    chromedriver_path: Optional[str] = None
    chromium_binary: Optional[str] = None

    # ── 截图存储（MinIO / S3，私有化）──────────────────────────────────────────
    # 上传到本地 MinIO，返回对象 key，由协调中枢同源代理下载
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "pentest-self-reports"
    minio_region: str = "us-east-1"
    minio_public: bool = False   # True 时返回预签名直链；False 返回对象 key（推荐，走协调中枢代理）

    # DNSLog defaults
    dnslog_domain: str = ""
    dnslog_token: str = ""
    dnslog_webserver: str = ""
    dnslog_type: str = "internal"
    callback_red_base_url: str = "https://callback.red"
    dnslog_cn_base_url: str = "http://www.dnslog.cn"

    class Config:
        env_file = ".env"
        extra = "ignore"


def get_image_storage_config() -> dict:
    """读取截图存储配置（MinIO）。"""
    try:
        config = ToolConfig()
        return {
            "minio": {
                "endpoint": config.minio_endpoint,
                "access_key": config.minio_access_key,
                "secret_key": config.minio_secret_key,
                "bucket": config.minio_bucket,
                "region": config.minio_region,
                "public": config.minio_public,
            },
        }
    except Exception:
        return {
            "minio": {
                "endpoint": ToolConfig.model_fields["minio_endpoint"].default,
                "access_key": "",
                "secret_key": "",
                "bucket": ToolConfig.model_fields["minio_bucket"].default,
                "region": ToolConfig.model_fields["minio_region"].default,
                "public": False,
            },
        }


def get_dnslog_config() -> dict:
    try:
        config = ToolConfig()
        return {
            "type": config.dnslog_type,
            "domain": config.dnslog_domain,
            "token": config.dnslog_token,
            "webserver": config.dnslog_webserver,
            "callback_red_base_url": config.callback_red_base_url,
            "dnslog_cn_base_url": config.dnslog_cn_base_url,
        }
    except Exception:
        return {
            "type": ToolConfig.model_fields["dnslog_type"].default,
            "domain": ToolConfig.model_fields["dnslog_domain"].default,
            "token": ToolConfig.model_fields["dnslog_token"].default,
            "webserver": ToolConfig.model_fields["dnslog_webserver"].default,
            "callback_red_base_url": ToolConfig.model_fields["callback_red_base_url"].default,
            "dnslog_cn_base_url": ToolConfig.model_fields["dnslog_cn_base_url"].default,
        }
    
