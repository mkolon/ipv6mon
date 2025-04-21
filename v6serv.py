#!/usr/bin/env python3
"""
IPv6 Connection Monitor - Server Component
Run this on the Raspberry Pi in Vermont
"""

import socket
import time
import json
import logging
import datetime
import threading
import argparse
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ipv6_monitor_server.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("ipv6-monitor-server")

class IPv6MonitorServer:
    def __init__(self, host='::', port=8888, data_dir='./data'):
        self.host = host
        self.port = port
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "start_time": time.time(),
            "client_history": {}
        }
        
        # Create lock for thread-safe operations
        self.stats_lock = threading.Lock()
    
    def save_request(self, client_addr, data):
        """Save request data to a file"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d")
        file_path = self.data_dir / f"requests_{timestamp}.json"
        
        entry = {
            "timestamp": time.time(),
            "client": client_addr,
            "data": data,
            "server_time": datetime.datetime.now().isoformat()
        }
        
        # Append to the daily file
        with open(file_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        # Update statistics
        with self.stats_lock:
            self.stats["total_requests"] += 1
            
            if client_addr not in self.stats["client_history"]:
                self.stats["client_history"][client_addr] = {
                    "first_seen": time.time(),
                    "request_count": 0
                }
            
            self.stats["client_history"][client_addr]["request_count"] += 1
            self.stats["client_history"][client_addr]["last_seen"] = time.time()
    
    def handle_client(self, client_socket, client_addr):
        """Handle an individual client connection"""
        logger.info(f"Connection from {client_addr}")
        
        try:
            # Receive data from client
            data = client_socket.recv(4096).decode('utf-8')
            
            if data:
                # Try to parse as JSON
                try:
                    client_data = json.loads(data)
                    logger.info(f"Received data: {client_data}")
                    
                    # Save the request data
                    self.save_request(client_addr[0], client_data)
                    
                    # Send response with server timestamp
                    response = {
                        "status": "success",
                        "server_time": time.time(),
                        "message": "Data received successfully"
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {data}")
                    response = {
                        "status": "error",
                        "message": "Invalid JSON data"
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {str(e)}")
        
        finally:
            client_socket.close()
    
    def start(self):
        """Start the IPv6 monitor server"""
        try:
            # Create IPv6 socket
            server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to the address and port
            server_socket.bind((self.host, self.port, 0, 0))
            
            # Listen for connections
            server_socket.listen(5)
            logger.info(f"Server started on [{self.host}]:{self.port}")
            
            while True:
                # Accept client connection
                client_socket, client_addr = server_socket.accept()
                
                # Handle client in a new thread
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_addr)
                )
                client_thread.daemon = True
                client_thread.start()
                
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
        
        finally:
            if 'server_socket' in locals():
                server_socket.close()

def main():
    """Main function to run the server"""
    parser = argparse.ArgumentParser(description='IPv6 Connection Monitor Server')
    parser.add_argument('--host', default='::', help='IPv6 address to bind to')
    parser.add_argument('--port', type=int, default=8888, help='Port to listen on')
    parser.add_argument('--data-dir', default='./data', help='Directory to store data')
    
    args = parser.parse_args()
    
    server = IPv6MonitorServer(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir
    )
    server.start()

if __name__ == "__main__":
    main()
