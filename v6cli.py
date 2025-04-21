#!/usr/bin/env python3
"""
IPv6 Connection Monitor - Client Component
Run this on the Digital Ocean VM in NYC
"""

import socket
import time
import json
import logging
import datetime
import argparse
import sys
import statistics
from pathlib import Path
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ipv6_monitor_client.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("ipv6-monitor-client")

class IPv6MonitorClient:
    def __init__(self, server_host, server_port=8888, interval=60, data_dir='./data'):
        self.server_host = server_host
        self.server_port = server_port
        self.interval = interval  # seconds between checks
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Statistics
        self.stats = {
            "checks": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "latency_history": [],
            "start_time": time.time()
        }
    
    def ping_test(self):
        """Run ping test to the server"""
        try:
            # Use subprocess to run ping6 command
            cmd = ["ping", "-6", "-c", "5", self.server_host]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Extract ping statistics
                output = result.stdout
                
                # Parse ping output (this is simplistic and may need adjustment)
                # Example line: "rtt min/avg/max/mdev = 14.723/17.331/20.458/2.333 ms"
                rtt_line = [line for line in output.split('\n') if "rtt min/avg/max/mdev" in line]
                if rtt_line:
                    rtt_stats = rtt_line[0].split(' = ')[1].split('/')
                    ping_data = {
                        "min": float(rtt_stats[0]),
                        "avg": float(rtt_stats[1]),
                        "max": float(rtt_stats[2]),
                        "mdev": float(rtt_stats[3].split()[0])
                    }
                    
                    # Parse packet loss
                    loss_line = [line for line in output.split('\n') if "packets transmitted" in line]
                    if loss_line:
                        parts = loss_line[0].split(',')
                        transmitted = int(parts[0].split()[0])
                        received = int(parts[1].split()[0])
                        loss_percent = float(parts[2].split()[0].replace('%', ''))
                        
                        ping_data["transmitted"] = transmitted
                        ping_data["received"] = received
                        ping_data["loss_percent"] = loss_percent
                    
                    return {
                        "success": True,
                        "ping": ping_data,
                        "raw_output": output
                    }
            
            return {
                "success": False,
                "error": "Ping failed",
                "raw_output": result.stdout + "\n" + result.stderr
            }
            
        except Exception as e:
            logger.error(f"Error during ping test: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_connection(self):
        """Perform a connection check to the IPv6 server"""
        timestamp = time.time()
        
        # First run a ping test
        ping_results = self.ping_test()
        
        # Initialize results
        results = {
            "timestamp": timestamp,
            "datetime": datetime.datetime.now().isoformat(),
            "server": self.server_host,
            "port": self.server_port,
            "ping_results": ping_results,
            "tcp_connection": {
                "success": False,
                "latency": None,
                "error": None
            }
        }
        
        # Now try TCP connection
        try:
            # Record start time for latency calculation
            start_time = time.time()
            
            # Create IPv6 socket
            client_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            client_socket.settimeout(10)  # 10-second timeout
            
            # Connect to server
            client_socket.connect((self.server_host, self.server_port, 0, 0))
            
            # Calculate initial connection latency
            connection_latency = time.time() - start_time
            
            # Prepare data to send
            data = {
                "client_time": timestamp,
                "message": "IPv6 connection check",
                "check_number": self.stats["checks"] + 1,
                "ping_successful": ping_results["success"]
            }
            
            # Add ping stats if available
            if ping_results["success"]:
                data["ping_stats"] = ping_results["ping"]
            
            # Send data to server
            client_socket.send(json.dumps(data).encode('utf-8'))
            
            # Wait for response
            response = client_socket.recv(4096).decode('utf-8')
            
            # Calculate total round-trip time
            rtt = time.time() - start_time
            
            # Parse server response
            try:
                server_response = json.loads(response)
                results["server_response"] = server_response
                
                # Update TCP connection results
                results["tcp_connection"]["success"] = True
                results["tcp_connection"]["latency"] = rtt
                results["tcp_connection"]["connection_latency"] = connection_latency
                
                # Update stats
                self.stats["successful_connections"] += 1
                self.stats["latency_history"].append(rtt)
                
                # Keep only the last 1000 latency values to avoid unbounded memory growth
                if len(self.stats["latency_history"]) > 1000:
                    self.stats["latency_history"] = self.stats["latency_history"][-1000:]
                
                logger.info(f"Successfully connected to server. RTT: {rtt:.4f}s")
                
            except json.JSONDecodeError:
                results["tcp_connection"]["error"] = "Invalid server response"
                logger.error(f"Invalid server response: {response}")
            
        except socket.timeout:
            results["tcp_connection"]["error"] = "Connection timeout"
            self.stats["failed_connections"] += 1
            logger.error("Connection timeout")
            
        except socket.error as e:
            results["tcp_connection"]["error"] = f"Socket error: {str(e)}"
            self.stats["failed_connections"] += 1
            logger.error(f"Socket error: {str(e)}")
            
        except Exception as e:
            results["tcp_connection"]["error"] = f"Error: {str(e)}"
            self.stats["failed_connections"] += 1
            logger.error(f"Error during connection check: {str(e)}")
            
        finally:
            if 'client_socket' in locals():
                client_socket.close()
            
            # Update check count
            self.stats["checks"] += 1
            
            # Save results to file
            self.save_results(results)
            
            return results
    
    def save_results(self, results):
        """Save check results to a file"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d")
        file_path = self.data_dir / f"checks_{timestamp}.json"
        
        with open(file_path, "a") as f:
            f.write(json.dumps(results) + "\n")
    
    def generate_report(self):
        """Generate a simple statistics report"""
        if self.stats["checks"] == 0:
            return "No checks performed yet."
        
        uptime_pct = (self.stats["successful_connections"] / self.stats["checks"]) * 100 if self.stats["checks"] > 0 else 0
        
        report = [
            f"IPv6 Monitor Report - {datetime.datetime.now().isoformat()}",
            f"======================================================",
            f"Server: [{self.server_host}]:{self.server_port}",
            f"Running since: {datetime.datetime.fromtimestamp(self.stats['start_time']).isoformat()}",
            f"Total checks: {self.stats['checks']}",
            f"Successful connections: {self.stats['successful_connections']}",
            f"Failed connections: {self.stats['failed_connections']}",
            f"Connection success rate: {uptime_pct:.2f}%"
        ]
        
        # Add latency statistics if we have data
        if self.stats["latency_history"]:
            latency_data = self.stats["latency_history"]
            report.extend([
                f"",
                f"Latency Statistics (seconds):",
                f"  Minimum: {min(latency_data):.4f}",
                f"  Maximum: {max(latency_data):.4f}",
                f"  Average: {sum(latency_data) / len(latency_data):.4f}",
                f"  Median: {statistics.median(latency_data):.4f}",
                f"  Std Dev: {statistics.stdev(latency_data) if len(latency_data) > 1 else 0:.4f}"
            ])
        
        return "\n".join(report)
    
    def start(self):
        """Start the monitoring loop"""
        logger.info(f"Starting IPv6 connection monitoring to [{self.server_host}]:{self.server_port}")
        
        try:
            while True:
                # Perform connection check
                self.check_connection()
                
                # Log statistics periodically
                if self.stats["checks"] % 10 == 0:
                    logger.info(self.generate_report())
                
                # Wait for the next interval
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            print(self.generate_report())
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
            sys.exit(1)

def main():
    """Main function to run the client"""
    parser = argparse.ArgumentParser(description='IPv6 Connection Monitor Client')
    parser.add_argument('server_host', help='IPv6 address of the server')
    parser.add_argument('--port', type=int, default=8888, help='Server port')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    parser.add_argument('--data-dir', default='./data', help='Directory to store data')
    parser.add_argument('--report', action='store_true', help='Generate a report and exit')
    
    args = parser.parse_args()
    
    client = IPv6MonitorClient(
        server_host=args.server_host,
        server_port=args.port,
        interval=args.interval,
        data_dir=args.data_dir
    )
    
    if args.report:
        # Just generate a report from existing data
        print(client.generate_report())
    else:
        # Start the monitoring loop
        client.start()

if __name__ == "__main__":
    main()
