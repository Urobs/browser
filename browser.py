import re
import socket, ssl, gzip
import chardet

MAX_REDIRECT = 10
class URL:
    def __init__(self, url: str, rd_count=0) -> None:
        self.view_source = False
        self.redirect = False
        self.rd_count = rd_count
        if url.startswith("data:"):
            self.scheme = "data"
            mediatype_and_encoding, self.data = url[5:].split(",", 1)
            if mediatype_and_encoding == "":
                self.mediatype = "text/plain"
                self.encoding = ""
            else:
                if ";" in mediatype_and_encoding:
                    self.mediatype, self.encoding = mediatype_and_encoding.split(";", 1)
                else:
                    self.mediatype = mediatype_and_encoding
                    self.encoding = ""
            return
        if url.startswith("view-source:"):
            url = url.replace("view-source:", "", 1)
            self.view_source = True
        self.scheme, url = url.split("://", 1)
        assert self.scheme in ["http", "https", "file"], "Unknown Scheme {}".format(
            self.scheme
        )
        if "/" not in url:
            url = url + "/"
        if self.scheme == "file":
            self.path = url
        else:
            self.host, url = url.split("/", 1)
            self.path = "/" + url
            if self.scheme == "http":
                self.port = 80
            elif self.scheme == "https":
                self.port = 443

            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)

    def read_local_file(self):
        content = ""
        with open(self.path, "r") as file:
            content = file.read()
        return content

    def request(self):
        if self.scheme == "data":
            return {
                "Content-Type": self.mediatype
            }, self.data
        if self.scheme == "file":
            return {}, self.read_local_file()
        conn = socket.socket(
            family=socket.AF_INET,  # through internet
            proto=socket.IPPROTO_TCP,  # tcp
            type=socket.SOCK_STREAM,  # arbitrary amounts of data
        )

        if self.scheme == "https":
            ctx = ssl.create_default_context()
            conn = ctx.wrap_socket(conn, server_hostname=self.host)

        conn.connect((self.host, self.port))  # connect to the other host

        custom_request_headers = {
            "Connection": "close",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
            "Accept-Encoding": "gzip",
        }
        custom_headers_string = "\r\n" + "\r\n".join(
            f"{k}: {v}" for k, v in custom_request_headers.items()
        )
        # encode and send the http message
        conn.send(
            ("GET {} HTTP/1.1\r\nHost: {}{}\r\n\r\n")
            .format(self.path, self.host, custom_headers_string)
            .encode("utf8")
        )

        # receive bytes data of headers and body
        statusline_and_header_data = b""
        body_data = b""

        while True:
            chunk = conn.recv(1024)
            if not chunk:
                raise Exception("Connection closed before headers was received")
            statusline_and_header_data += chunk
            if b"\r\n\r\n" in chunk:
                statusline, remaining = statusline_and_header_data.split(b"\r\n\r\n", 1)
                body_data += remaining
                break

        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            body_data += chunk

        conn.close()

        # Decode the headers
        statusline_and_headers = statusline_and_header_data.decode(
            "ascii", errors="ignore"
        )
        statusline, headers = statusline_and_headers.split("\r\n", 1)
        version, status, explanation = statusline.split(" ", 2)
        if status.startswith("3"):
            self.redirect = True
        # assert status == "200", "{}: {}".format(status, explanation)

        # parse headers
        headers_obj = {}
        header_lines = headers.split("\r\n")
        while True:
            line = header_lines.pop(0)
            if line == "":
                break
            header, value = line.split(":", 1)
            headers_obj[header.lower()] = value.strip()

        if headers_obj.get("transfer-encoding") == "chunked":
            chunks = []
            while True:
                # Find the position of the first \r\n, which ends the chunk size
                chunk_size_end_pos = body_data.find(b"\r\n")
                # Get the chunk size and convert it from hex to int
                chunk_size = int(body_data[:chunk_size_end_pos].decode("ascii"), 16)
                # If chunk size is 0, it's the last chunk
                if chunk_size == 0:
                    break
                # Start position of the chunk data
                chunk_start_pos = chunk_size_end_pos + 2  # 2 for \r\n
                # End position of the chunk data
                chunk_end_pos = chunk_start_pos + chunk_size
                # Append the chunk to our chunks list
                chunks.append(body_data[chunk_start_pos:chunk_end_pos])
                # Set the remaining body data for the next iteration
                body_data = body_data[chunk_end_pos + 2 :]  # 2 for \r\n
            # Concatenate all chunks to get the actual body
            body_data = b"".join(chunks)

        if headers_obj.get("content-encoding") == "gzip":
            body_data = gzip.decompress(body_data)
        if self.redirect and headers_obj.get("location"):
            if self.rd_count > MAX_REDIRECT:
                return self.view_source, headers_obj, "重定向次数过多"
            location = headers_obj.get("location")
            if len(location.split("://", 1)) == 1:
                location = "{}://{}{}".format(self.scheme, self.host, location)
            n_url = URL(location, self.rd_count + 1)
            return n_url.request()
        # guess encoding by html body
        detect = chardet.detect(body_data)
        encoding = detect.get("encoding")
        if encoding == "GB2312":
            encoding = "GBK"  # GBK is a superset of GB2312

        body = body_data.decode(encoding=encoding, errors="replace")

        return self.view_source, headers_obj, body

def show(body: str):
    maybe_entity = False
    is_entity = False
    collect = ''
    lt = "&lt;"
    gt = "&gt;"
    
    str_2_entity = {
        gt: ">",
        lt: "<"
    }
    
    result = ""
    for c in body:
        if c == "&":
            collect += c
            maybe_entity = True
        elif c == ";" and maybe_entity:
            maybe_entity = False
            collect += c
            if collect in str_2_entity.keys():
                is_entity = True
            else:
                collect = ""
        elif maybe_entity:
            collect += c
            
        if is_entity:
            result = result[:(-(len(collect) - 1))] + str_2_entity[collect]
            is_entity = False
            collect = ""
            
        else:
            result += c
    print(result)
            

def transform(body: str):
    is_in_tag = False
    tag = ''
    is_in_body = False
    result = ''
    
    # check if in tag
    # check what the tag is
    # check if in body
    for c in body:
        if c == '<':
            tag = ''
            is_in_tag = True
        elif c == '>':
            is_in_tag = False
            if tag == 'body':
                is_in_body = True
            elif tag == '/body':
                is_in_body = False
        elif is_in_tag:
            tag += c
        elif is_in_body:
            result += c

    return result
    

def load(url: URL):
    view_source, headers, body = url.request()
    if view_source:
        show(body)
    else:
        show(transform(body))
        


if __name__ == "__main__":
    import sys

    load(URL(sys.argv[1]))
