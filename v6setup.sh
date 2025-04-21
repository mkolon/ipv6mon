#!/bin/bash

# IPv6 Connection Monitor - Setup Script
# This script helps set up the monitor on both server and client machines

# Text formatting
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print section headers
print_header() {
    echo -e "\n${BOLD}${GREEN}=== $1 ===${NC}\n"
}

# Function to print errors
print_error() {
    echo -e "${RED}ERROR: $1${NC}"
}

# Function to print warnings
print_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

# Function to check if a command exists
check_command() {
    command -v $1 >/dev/null 2>&1
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_warning "This script is not running as root. Some operations may fail."
        print_warning "Consider running with sudo if you encounter permission issues."
        sleep 2
    fi
}

# Function to check and install Python packages
install_python_packages() {
    print_header "Checking Python Packages"
    
    # Check if pip is installed
    if ! check_command pip3; then
        print_error "pip3 is not installed!"
        echo "Please install pip3 first and run this script again."
        echo "On Debian/Ubuntu: sudo apt-get install python3-pip"
        echo "On Raspberry Pi OS: sudo apt-get install python3-pip"
        exit 1
    fi
    
    # Required packages
    PACKAGES=("matplotlib" "pandas" "numpy")
    
    for pkg in "${PACKAGES[@]}"; do
        echo -n "Checking for $pkg... "
        if python3 -c "import $pkg" >/dev/null 2>&1; then
            echo -e "${GREEN}Installed${NC}"
        else
            echo -e "${YELLOW}Not found${NC}"
            echo "Installing $pkg..."
            pip3 install $pkg
            if [ $? -ne 0 ]; then
                print_error "Failed to install $pkg. Please install it manually."
                echo "pip3 install $pkg"
            fi
        fi
    done
}

# Setup server function
setup_server() {
    print_header "Setting up IPv6 Monitor Server (Raspberry Pi)"
    
    # Create directory structure
    mkdir -p ./data
    
    # Check if server script exists
    if [ ! -f "ipv6_monitor_server.py" ]; then
        print_error "ipv6_monitor_server.py not found in current directory!"
        echo "Please ensure you have downloaded all the necessary scripts."
        exit 1
    fi
    
    # Make server script executable
    chmod +x ipv6_monitor_server.py
    
    # Create systemd service file for autostart
    echo "Creating systemd service file..."
    SERVICE_FILE="ipv6-monitor-server.service"
    
    # Get current directory and user
    CURRENT_DIR=$(pwd)
    CURRENT_USER=$(whoami)
    
    cat > $SERVICE_FILE << EOF
[Unit]
Description=IPv6 Connection Monitor Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 ${CURRENT_DIR}/ipv6_monitor_server.py
WorkingDirectory=${CURRENT_DIR}
StandardOutput=inherit
StandardError=inherit
Restart=always
User=${CURRENT_USER}

[Install]
WantedBy=multi-user.target
EOF
    
    echo "Service file created: $SERVICE_FILE"
    echo "To install the service, run:"
    echo "  sudo cp $SERVICE_FILE /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable ipv6-monitor-server"
    echo "  sudo systemctl start ipv6-monitor-server"
    
    # Check IPv6 connectivity
    print_header "Checking IPv6 Connectivity"
    
    # Get IPv6 address
    IPV6_ADDR=$(ip -6 addr show scope global | grep -v fe80 | grep -oP '(?<=inet6 )[\da-f:]+')
    
    if [ -z "$IPV6_ADDR" ]; then
        print_warning "No global IPv6 address found!"
        echo "This machine may not have IPv6 connectivity."
        echo "Please ensure IPv6 is properly configured on your network."
    else
        echo "IPv6 addresses found:"
        echo "$IPV6_ADDR"
    fi
    
    # Test ping to well-known IPv6 hosts
    echo "Testing IPv6 connectivity..."
    if ping6 -c 3 2001:4860:4860::8888 > /dev/null 2>&1; then
        echo -e "${GREEN}IPv6 connectivity confirmed (Google DNS reachable)${NC}"
    else
        print_warning "Cannot reach Google DNS over IPv6. There might be connectivity issues."
    fi
    
    print_header "Server Setup Complete"
    echo "To manually start the server: ./ipv6_monitor_server.py"
    echo "Server will listen on all interfaces, port 8888 by default."
    echo "Make sure this port is accessible through your firewall."
}

# Setup client function
setup_client() {
    print_header "Setting up IPv6 Monitor Client (Digital Ocean VM)"
    
    # Create directory structure
    mkdir -p ./data ./reports
    
    # Check if client script exists
    if [ ! -f "ipv6_monitor_client.py" ]; then
        print_error "ipv6_monitor_client.py not found in current directory!"
        echo "Please ensure you have downloaded all the necessary scripts."
        exit 1
    fi
    
    # Check if analysis script exists
    if [ ! -f "ipv6_monitor_analysis.py" ]; then
        print_warning "ipv6_monitor_analysis.py not found in current directory!"
        echo "The analysis tool will not be available."
    else
        chmod +x ipv6_monitor_analysis.py
    fi
    
    # Make client script executable
    chmod +x ipv6_monitor_client.py
    
    # Prompt for server address
    read -p "Enter your Raspberry Pi's IPv6 address: " SERVER_IPV6
    
    # Create systemd service file for autostart
    echo "Creating systemd service file..."
    SERVICE_FILE="ipv6-monitor-client.service"
    
    # Get current directory and user
    CURRENT_DIR=$(pwd)
    CURRENT_USER=$(whoami)
    
    cat > $SERVICE_FILE << EOF
[Unit]
Description=IPv6 Connection Monitor Client
After=network.target

[Service]
ExecStart=/usr/bin/python3 ${CURRENT_DIR}/ipv6_monitor_client.py ${SERVER_IPV6} --interval 300
WorkingDirectory=${CURRENT_DIR}
StandardOutput=inherit
StandardError=inherit
Restart=always
User=${CURRENT_USER}

[Install]
WantedBy=multi-user.target
EOF
    
    echo "Service file created: $SERVICE_FILE"
    echo "To install the service, run:"
    echo "  sudo cp $SERVICE_FILE /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable ipv6-monitor-client"
    echo "  sudo systemctl start ipv6-monitor-client"
    
    # Create a simple cron job for the analysis
    if [ -f "ipv6_monitor_analysis.py" ]; then
        echo "Creating a cron job for daily reports..."
        CRON_JOB="0 0 * * * cd ${CURRENT_DIR} && python3 ipv6_monitor_analysis.py --report-only > /dev/null 2>&1"
        
        # Add to crontab
        (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
        
        echo "Cron job added to generate daily reports."
    fi
    
    # Test connection to server
    print_header "Testing Connection to Server"
    
    echo "Testing IPv6 connectivity to server..."
    if ping6 -c 3 $SERVER_IPV6 > /dev/null 2>&1; then
        echo -e "${GREEN}Server is reachable over IPv6${NC}"
        
        # Test TCP connection
        echo "Testing TCP connection to server port 8888..."
        nc -z -v -w 5 $SERVER_IPV6 8888 > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}TCP connection successful${NC}"
        else
            print_warning "Cannot connect to server port 8888."
            echo "Please ensure the server is running and the port is accessible."
        fi
        
    else
        print_warning "Cannot reach server over IPv6. Please check connectivity or firewall rules."
    fi
    
    print_header "Client Setup Complete"
    echo "To manually start the client: ./ipv6_monitor_client.py $SERVER_IPV6"
    echo "To generate a report: ./ipv6_monitor_analysis.py"
}

# Main script execution starts here
print_header "IPv6 Connection Monitor Setup"
echo "This script will help you set up the IPv6 monitoring system."

# Check if running as root
check_root

# Install required packages
install_python_packages

# Ask user whether this is server or client
echo -e "\nIs this the ${BOLD}server${NC} (Raspberry Pi in Vermont) or the ${BOLD}client${NC} (VM in NYC)?"
select type in "Server" "Client"; do
    case $type in
        Server )
            setup_server
            break;;
        Client )
            setup_client
            break;;
        * )
            echo "Please select 1 or 2";;
    esac
done

print_header "Setup Complete"
echo "The IPv6 Connection Monitor is now set up."
echo "For more information, refer to the documentation."
