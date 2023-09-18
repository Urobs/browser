import socket, ssl
import chardet
class URL:
    def __init__(self, url: str) -> None:
        self.scheme, url = url.split("://", 1)
        assert self.scheme in ["http", "https"], \
            "Unknown Scheme {}".format(self.scheme)
        if "/" not in url:
            url = url + "/"
        self.host, url = url.split("/", 1)
        self.path = "/" + url
        if self.scheme == "http":
            self.port = 80
        elif self.scheme == "https":
            self.port = 443
        
        if ":" in self.host:
            self.host, port = self.host.split(":", 1)
            self.port = int(port)
    def request(self):
        conn = socket.socket(
            family=socket.AF_INET, # through internet
            proto=socket.IPPROTO_TCP, # tcp 
            type=socket.SOCK_STREAM # arbitrary amounts of data
        )
        
        if self.scheme == "https":
            ctx = ssl.create_default_context()
            conn = ctx.wrap_socket(conn, server_hostname=self.host)
        
        conn.connect((self.host, self.port)) # connect to the other host
        
        custom_request_headers = {
            "Connection": "close",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
        }
        custom_headers_string = "\r\n" + "\r\n".join(f"{k}: {v}" for k, v in custom_request_headers.items())
        # encode and send the http message
        conn.send(("GET {} HTTP/1.1\r\nHost: {}{}\r\n\r\n").format(self.path, self.host, custom_headers_string).encode("utf8"))
        
        # receive bytes data of headers and body
        statusline_and_header_data = b''
        body_data = b''
        
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                raise Exception('Connection closed before headers was received')
            statusline_and_header_data += chunk
            if b'\r\n\r\n' in chunk:
                statusline, remaining = statusline_and_header_data.split(b'\r\n\r\n', 1)
                body_data += remaining
                break

        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            body_data += chunk

        conn.close()

        # guess encoding by html body
        detect = chardet.detect(body_data)
        encoding = detect.get("encoding")
        if encoding == 'GB2312':
            encoding = 'GBK' # GBK is a superset of GB2312 
        
        # parse status line of headers
        statusline_and_headers = statusline_and_header_data.decode(encoding=encoding, errors="replace")
        statusline, headers = statusline_and_headers.split("\r\n", 1)
        version, status, explanation = statusline.split(" ", 2)
        assert status == "200", "{}: {}".format(status, explanation)
        
        # parse headers
        headers_obj = {}
        header_lines = headers.split("\r\n")     
        while True:
            line = header_lines.pop(0)
            if line == "":
                break
            header, value = line.split(":", 1)
            headers_obj[header.lower()] = value.strip()
        
        assert "transfer-encoding" not in headers_obj
        assert "content-encoding" not in headers_obj
        
        body = body_data.decode(encoding=encoding, errors='replace')
        
        return headers_obj, body
    
def show(body: str):
    in_angle = False
    for c in body:
        if c == "<":
            in_angle = True
        elif c == ">":
            in_angle = False
        elif not in_angle:
            print(c, end="")
                
def load(url: URL):
    headers, body = url.request()
    # show(body)
    print(headers)
    
if __name__ == '__main__':
    import sys
    load(URL(sys.argv[1]))