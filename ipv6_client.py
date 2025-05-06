# ipv6_client.py
import socket
import sys

SERVER_ADDR = '2604:a880:400:d1:0:1:8de1:3001'  # e.g., '2601:abcd::1234'
PORT = 65432

try:
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.settimeout(3)
        s.connect((SERVER_ADDR, PORT))
        s.sendall(b'ping6')
        data = s.recv(1024)
        if data == b'pong6':
            print("Server reachable via IPv6.")
        else:
            print("Server responded with unexpected data.")
except socket.timeout:
    print("Timeout: server unreachable.")
except Exception as e:
    print(f"Connection failed: {e}")
