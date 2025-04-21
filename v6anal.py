#!/usr/bin/env python3
"""
IPv6 Connection Monitor - Analysis Tool
Use this to analyze and visualize the collected data
"""

import json
import glob
import argparse
import datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

def load_data(data_dir, days=7):
    """Load data from the specified directory for the last N days"""
    data_dir = Path(data_dir)
    
    # Calculate date range
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)
    
    # Find all check files in the date range
    all_files = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        file_pattern = str(data_dir / f"checks_{date_str}.json")
        all_files.extend(glob.glob(file_pattern))
        current_date += datetime.timedelta(days=1)
    
    # Load data from files
    data = []
    for file_path in sorted(all_files):
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    data.append(entry)
                except json.JSONDecodeError:
                    print(f"Error parsing line in {file_path}")
    
    return data

def analyze_data(data):
    """Analyze the loaded data and create a DataFrame"""
    if not data:
        print("No data found for the specified period.")
        return None
    
    # Extract relevant fields
    results = []
    for entry in data:
        # Basic information
        timestamp = entry.get('timestamp')
        datetime_str = entry.get('datetime')
        
        # TCP connection info
        tcp_success = entry.get('tcp_connection', {}).get('success', False)
        tcp_latency = entry.get('tcp_connection', {}).get('latency')
        tcp_error = entry.get('tcp_connection', {}).get('error')
        
        # Ping info
        ping_success = entry.get('ping_results', {}).get('success', False)
        
        ping_min = None
        ping_avg = None
        ping_max = None
        ping_loss = None
        
        if ping_success and 'ping' in entry.get('ping_results', {}):
            ping_data = entry['ping_results']['ping']
            ping_min = ping_data.get('min')
            ping_avg = ping_data.get('avg')
            ping_max = ping_data.get('max')
            ping_loss = ping_data.get('loss_percent')
        
        results.append({
            'timestamp': timestamp,
            'datetime': datetime_str,
            'tcp_success': tcp_success,
            'tcp_latency': tcp_latency,
            'tcp_error': tcp_error,
            'ping_success': ping_success,
            'ping_min': ping_min,
            'ping_avg': ping_avg,
            'ping_max': ping_max,
            'ping_loss': ping_loss
        })
    
    # Convert to DataFrame
    df = pd.DataFrame(results)
    
    # Convert timestamp to datetime for easier analysis
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # Sort by datetime
    df = df.sort_values('datetime')
    
    return df

def generate_plots(df, output_dir='.'):
    """Generate visualization plots"""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Set default figure size
    plt.figure(figsize=(12, 7))
    
    # Plot 1: TCP Connection Success Rate over time
    plt.figure(figsize=(12, 7))
    df['success_rolling'] = df['tcp_success'].rolling(window=10).mean()
    plt.plot(df['datetime'], df['success_rolling'], label='Connection Success Rate (10-point rolling avg)')
    plt.scatter(df['datetime'], df['tcp_success'], alpha=0.3, label='Individual Checks')
    plt.xlabel('Date/Time')
    plt.ylabel('Success Rate')
    plt.title('IPv6 Connection Success Rate Over Time')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / 'connection_success_rate.png')
    plt.close()
    
    # Plot 2: TCP Connection Latency over time
    plt.figure(figsize=(12, 7))
    # Filter out failed connections
    latency_df = df[df['tcp_success'] == True].copy()
    if not latency_df.empty:
        plt.plot(latency_df['datetime'], latency_df['tcp_latency'], label='TCP Round-Trip Time')
        
        # Add rolling average
        latency_df['latency_rolling'] = latency_df['tcp_latency'].rolling(window=10).mean()
        plt.plot(latency_df['datetime'], latency_df['latency_rolling'], 'r-', 
                 label='10-point Rolling Average', linewidth=2)
        
        plt.xlabel('Date/Time')
        plt.ylabel('Latency (seconds)')
        plt.title('IPv6 Connection Latency Over Time')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / 'connection_latency.png')
    plt.close()
    
    # Plot 3: Ping Latency over time
    plt.figure(figsize=(12, 7))
    # Filter for successful pings
    ping_df = df[df['ping_success'] == True].copy()
    if not ping_df.empty:
        plt.plot(ping_df['datetime'], ping_df['ping_avg'], label='Average Ping')
        plt.fill_between(ping_df['datetime'], 
                         ping_df['ping_min'], 
                         ping_df['ping_max'], 
                         alpha=0.2, 
                         label='Min/Max Range')
        
        plt.xlabel('Date/Time')
        plt.ylabel('Ping Latency (ms)')
        plt.title('IPv6 Ping Latency Over Time')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / 'ping_latency.png')
    plt.close()
    
    # Plot 4: Packet Loss over time
    plt.figure(figsize=(12, 7))
    # Filter for successful pings with packet loss data
    loss_df = ping_df[ping_df['ping_loss'].notna()].copy()
    if not loss_df.empty:
        plt.plot(loss_df['datetime'], loss_df['ping_loss'], 'o-')
        plt.xlabel('Date/Time')
        plt.ylabel('Packet Loss (%)')
        plt.title('IPv6 Packet Loss Over Time')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / 'packet_loss.png')
    plt.close()
    
    # Plot 5: Daily success rate heatmap
    plt.figure(figsize=(12, 7))
    # Add hour and day columns
    df['hour'] = df['datetime'].dt.hour
    df['date'] = df['datetime'].dt.date
    
    # Group by date and hour, calculate success rate
    heatmap_data = df.groupby(['date', 'hour'])['tcp_success'].mean().unstack()
    
    # Plot heatmap if we have data
    if not heatmap_data.empty:
        plt.pcolormesh(heatmap_data.columns, range(len(heatmap_data.index)), heatmap_data.values, 
                       cmap='RdYlGn', vmin=0, vmax=1)
        plt.colorbar(label='Success Rate')
        plt.xlabel('Hour of Day')
        plt.ylabel('Date')
        plt.title('IPv6 Connection Success Rate by Hour')
        plt.yticks(np.arange(0.5, len(heatmap_data.index)), [d.strftime('%Y-%m-%d') for d in heatmap_data.index])
        plt.tight_layout()
        plt.savefig(output_dir / 'daily_success_heatmap.png')
    plt.close()
    
    print(f"Plots saved to {output_dir}")

def generate_report(df, output_file=None):
    """Generate a summary report"""
    if df is None or df.empty:
        return "No data available for analysis."
    
    # Calculate summary statistics
    total_checks = len(df)
    successful_connections = df['tcp_success'].sum()
    success_rate = (successful_connections / total_checks) * 100 if total_checks > 0 else 0
    
    # Calculate latency statistics for successful connections
    latency_df = df[df['tcp_success'] == True]
    if not latency_df.empty:
        avg_latency = latency_df['tcp_latency'].mean()
        min_latency = latency_df['tcp_latency'].min()
        max_latency = latency_df['tcp_latency'].max()
        median_latency = latency_df['tcp_latency'].median()
    else:
        avg_latency = min_latency = max_latency = median_latency = None
    
    # Calculate ping statistics
    ping_df = df[df['ping_success'] == True]
    if not ping_df.empty:
        avg_ping = ping_df['ping_avg'].mean()
        min_ping = ping_df['ping_min'].min()
        max_ping = ping_df['ping_max'].max()
        avg_packet_loss = ping_df['ping_loss'].mean()
    else:
        avg_ping = min_ping = max_ping = avg_packet_loss = None
    
    # Generate report
    report = [
        "IPv6 Connection Monitoring Report",
        "================================",
        "",
        f"Period: {df['datetime'].min()} to {df['datetime'].max()}",
        f"Total checks: {total_checks}",
        f"Successful connections: {successful_connections} ({success_rate:.2f}%)",
        f"Failed connections: {total_checks - successful_connections} ({100 - success_rate:.2f}%)",
        "",
        "TCP Connection Latency (seconds):",
        f"  Average: {avg_latency:.4f}" if avg_latency is not None else "  Average: N/A",
        f"  Minimum: {min_latency:.4f}" if min_latency is not None else "  Minimum: N/A",
        f"  Maximum: {max_latency:.4f}" if max_latency is not None else "  Maximum: N/A",
        f"  Median: {median_latency:.4f}" if median_latency is not None else "  Median: N/A",
        "",
        "Ping Statistics (ms):",
        f"  Average ping: {avg_ping:.2f}" if avg_ping is not None else "  Average ping: N/A",
        f"  Minimum ping: {min_ping:.2f}" if min_ping is not None else "  Minimum ping: N/A",
        f"  Maximum ping: {max_ping:.2f}" if max_ping is not None else "  Maximum ping: N/A",
        f"  Average packet loss: {avg_packet_loss:.2f}%" if avg_packet_loss is not None else "  Average packet loss: N/A",
        "",
        "Common failure reasons:",
    ]
    
    # Add common failure reasons
    error_df = df[df['tcp_success'] == False]
    if not error_df.empty:
        error_counts = error_df['tcp_error'].value_counts()
        for error, count in error_counts.items():
            if pd.notna(error):
                report.append(f"  {error}: {count} times ({count/len(error_df)*100:.2f}%)")
    else:
        report.append("  No failures recorded")
    
    # Write to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            f.write('\n'.join(report))
        print(f"Report saved to {output_file}")
    
    return '\n'.join(report)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='IPv6 Connection Monitor Analysis Tool')
    parser.add_argument('--data-dir', default='./data', help='Directory containing monitoring data')
    parser.add_argument('--output-dir', default='./reports', help='Directory to save outputs')
    parser.add_argument('--days', type=int, default=7, help='Number of days to analyze')
    parser.add_argument('--report-only', action='store_true', help='Generate report only (no plots)')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Load and analyze data
    print(f"Loading data from {args.data_dir} for the last {args.days} days...")
    data = load_data(args.data_dir, days=args.days)
    
    if not data:
        print("No data found. Please check that the data directory is correct.")
        