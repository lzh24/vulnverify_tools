import requests
import urllib.parse
import logging
import urllib3
import base64
import mimetypes

from core.config import get_image_storage_config

# 禁用不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def download_image_as_base64(url):
    """
    下载图片并转换为Base64编码
    :param url: 图片URL
    :return: Base64编码字符串 (包含 data:image/xxx;base64, 前缀)
    """
    if not url:
        return None

    try:
        logger.info(f"Start downloading image from: {url}")
        # 下载图片
        response = requests.get(url, verify=False, timeout=30)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')

            # 尝试根据文件内容推断 Content-Type (Magic Numbers)
            content_head = response.content[:12]
            detected_type = None

            if content_head.startswith(b'\xFF\xD8\xFF'):
                detected_type = 'image/jpeg'
            elif content_head.startswith(b'\x89PNG\r\n\x1a\n'):
                detected_type = 'image/png'
            elif content_head.startswith(b'GIF87a') or content_head.startswith(b'GIF89a'):
                detected_type = 'image/gif'
            elif content_head.startswith(b'RIFF') and content_head[8:12] == b'WEBP':
                detected_type = 'image/webp'
            elif content_head.startswith(b'BM'):
                detected_type = 'image/bmp'

            # 如果检测到了真实类型，优先使用真实类型
            if detected_type:
                content_type = detected_type
            else:
                # 否则尝试根据URL后缀推断
                parsed_url = urllib.parse.urlparse(url)
                mime_type, _ = mimetypes.guess_type(parsed_url.path)

                # 如果Header里的Content-Type不是图片，或者为空，或者通过URL猜出的类型更具体且是图片，则优先使用URL猜出的类型
                if not content_type or 'image' not in content_type or content_type == 'application/octet-stream':
                    if mime_type and 'image' in mime_type:
                        content_type = mime_type
                    else:
                        # 如果都无法判断，默认使用 image/jpeg
                        if not content_type or 'image' not in content_type:
                            content_type = 'image/jpeg'

            # 清理 Content-Type，移除参数 (如 ;charset=utf-8)
            if content_type:
                content_type = content_type.split(';')[0].strip()

            # 规范化 content_type
            if content_type == 'image/jpg':
                content_type = 'image/jpeg'

            # 再次检查，如果 content_type 仍然无效，强制默认为 image/jpeg
            if not content_type or 'image' not in content_type:
                content_type = 'image/jpeg'

            logger.info(f"Image downloaded successfully. Resolved Content-Type: {content_type}")

            base64_data = base64.b64encode(response.content).decode('utf-8')
            return f"data:{content_type};base64,{base64_data}"
        else:
            logger.error(f"Failed to download image from {url}: {response.status_code}")
            return None  # 下载失败返回 None，以便调用方处理
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
        return None  # 出错返回 None


def upload_to_minio(file_bytes) -> str | None:
    """上传截图到 MinIO/S3，返回对象 key（私有化默认路径）。

    - minio_public=True → 返回预签名直链（需公网可达）
    - minio_public=False（默认）→ 返回对象 key，由协调中枢同源代理下载
    """
    if not file_bytes:
        return None
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except Exception as exc:  # pragma: no cover - 依赖缺失时给出明确报错
        logger.error("boto3 not available for minio upload: %s", exc)
        return None

    cfg = get_image_storage_config().get("minio") or {}
    endpoint = cfg.get("endpoint") or ""
    access_key = cfg.get("access_key") or ""
    secret_key = cfg.get("secret_key") or ""
    bucket = cfg.get("bucket") or ""
    region = cfg.get("region") or "us-east-1"
    public = bool(cfg.get("public"))

    if not endpoint or not access_key or not secret_key or not bucket:
        logger.warning("minio config incomplete, skip upload (endpoint=%s bucket=%s)", endpoint, bucket)
        return None

    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(signature_version="s3v4"),
        )
        ext = "png"
        if file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            ext = "png"
        elif file_bytes[:3] == b"\xff\xd8\xff":
            ext = "jpg"
        elif file_bytes[:6] in (b"GIF87a", b"GIF89a"):
            ext = "gif"
        import uuid
        key = f"screenshots/{uuid.uuid4().hex}.{ext}"
        client.put_object(
            Bucket=bucket, Key=key, Body=file_bytes,
            ContentType=f"image/{ext}",
        )
        if public:
            url = client.generate_presigned_url(
                "get_object", Params={"Bucket": bucket, "Key": key},
                ExpiresIn=3600,
            )
            return url
        return key
    except Exception as exc:
        logger.error("minio upload failed: %s", exc)
        return None


def upload_and_get_url(file_bytes):
    """上传截图到 MinIO，返回对象 key（minio_public=true 时为预签名 URL）。"""
    return upload_to_minio(file_bytes)
