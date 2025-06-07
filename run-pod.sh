#!/bin/bash

# Ezra Bot Pod Management Script
# This script manages a podman pod with both the main bot and userbot containers

POD_NAME="ezra-pod"
MAIN_CONTAINER="ezra-telegram-bot"
USERBOT_CONTAINER="ezra-userbot-cron"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if pod exists
pod_exists() {
    podman pod exists "$POD_NAME" 2>/dev/null
}

# Function to check if container exists
container_exists() {
    podman container exists "$1" 2>/dev/null
}

# Function to create the pod
create_pod() {
    print_status "Creating pod: $POD_NAME"
    
    if pod_exists; then
        print_warning "Pod $POD_NAME already exists"
        return 0
    fi
    
    podman pod create \
        --name "$POD_NAME" \
        --share net \
        --infra-image k8s.gcr.io/pause:3.5 \
        --replace
    
    if [ $? -eq 0 ]; then
        print_status "Pod $POD_NAME created successfully"
    else
        print_error "Failed to create pod $POD_NAME"
        return 1
    fi
}

# Function to build images
build_images() {
    print_status "Building container images..."
    
    # Build main bot image
    print_status "Building main bot image..."
    podman build -t localhost/ezra-bot:latest -f Dockerfile .
    
    if [ $? -ne 0 ]; then
        print_error "Failed to build main bot image"
        return 1
    fi
    
    # Build userbot image
    print_status "Building userbot image..."
    podman build -t localhost/ezra-userbot:latest -f Dockerfile.userbot .
    
    if [ $? -ne 0 ]; then
        print_error "Failed to build userbot image"
        return 1
    fi
    
    print_status "Images built successfully"
}

# Function to start the main bot container
start_main_bot() {
    print_status "Starting main bot container..."
    
    if container_exists "$MAIN_CONTAINER"; then
        print_warning "Removing existing container: $MAIN_CONTAINER"
        podman rm -f "$MAIN_CONTAINER"
    fi
    
    podman run -d \
        --name "$MAIN_CONTAINER" \
        --pod "$POD_NAME" \
        --restart unless-stopped \
        -v "./data:/app/data:Z" \
        -e "DATABASE_PATH=/app/data/ezra.db" \
        --env-file .env \
        localhost/ezra-bot:latest
    
    if [ $? -eq 0 ]; then
        print_status "Main bot container started successfully"
    else
        print_error "Failed to start main bot container"
        return 1
    fi
}

# Function to start the userbot container
start_userbot() {
    print_status "Starting userbot container..."
    
    if container_exists "$USERBOT_CONTAINER"; then
        print_warning "Removing existing container: $USERBOT_CONTAINER"
        podman rm -f "$USERBOT_CONTAINER"
    fi
    
    podman run -d \
        --name "$USERBOT_CONTAINER" \
        --pod "$POD_NAME" \
        --restart unless-stopped \
        -v "./data:/app/data:Z" \
        -v "./config:/app/config:Z" \
        -e "DATABASE_PATH=/app/data/ezra.db" \
        -e "TELEGRAM_FOLDER_NAME=${TELEGRAM_FOLDER_NAME:-AI}" \
        --env-file config/credentials.env \
        localhost/ezra-userbot:latest
    
    if [ $? -eq 0 ]; then
        print_status "Userbot container started successfully"
    else
        print_error "Failed to start userbot container"
        return 1
    fi
}

# Function to stop the pod
stop_pod() {
    print_status "Stopping pod: $POD_NAME"
    
    if pod_exists; then
        podman pod stop "$POD_NAME"
        print_status "Pod $POD_NAME stopped"
    else
        print_warning "Pod $POD_NAME does not exist"
    fi
}

# Function to remove the pod
remove_pod() {
    print_status "Removing pod: $POD_NAME"
    
    if pod_exists; then
        podman pod rm -f "$POD_NAME"
        print_status "Pod $POD_NAME removed"
    else
        print_warning "Pod $POD_NAME does not exist"
    fi
}

# Function to show status
show_status() {
    print_status "Pod and container status:"
    echo
    
    if pod_exists; then
        echo "Pod Status:"
        podman pod ps --filter "name=$POD_NAME"
        echo
        echo "Container Status:"
        podman ps --filter "pod=$POD_NAME"
    else
        print_warning "Pod $POD_NAME does not exist"
    fi
}

# Function to show logs
show_logs() {
    local container="$1"
    local lines="${2:-50}"
    
    if [ -z "$container" ]; then
        print_error "Please specify container: main|userbot"
        return 1
    fi
    
    case "$container" in
        "main")
            if container_exists "$MAIN_CONTAINER"; then
                print_status "Showing logs for main bot (last $lines lines):"
                podman logs --tail "$lines" "$MAIN_CONTAINER"
            else
                print_error "Main bot container does not exist"
            fi
            ;;
        "userbot")
            if container_exists "$USERBOT_CONTAINER"; then
                print_status "Showing logs for userbot (last $lines lines):"
                podman logs --tail "$lines" "$USERBOT_CONTAINER"
            else
                print_error "Userbot container does not exist"
            fi
            ;;
        *)
            print_error "Invalid container. Use: main|userbot"
            ;;
    esac
}

# Function to restart the pod
restart_pod() {
    print_status "Restarting pod: $POD_NAME"
    stop_pod
    sleep 2
    start_pod
}

# Function to start the complete pod
start_pod() {
    print_status "Starting Ezra Bot Pod..."
    
    # Create pod if it doesn't exist
    if ! pod_exists; then
        create_pod || return 1
    fi
    
    # Start containers
    start_main_bot || return 1
    start_userbot || return 1
    
    print_status "Pod started successfully!"
    echo
    show_status
}

# Main command handling
case "$1" in
    "start")
        start_pod
        ;;
    "stop")
        stop_pod
        ;;
    "restart")
        restart_pod
        ;;
    "remove")
        remove_pod
        ;;
    "build")
        build_images
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs "$2" "$3"
        ;;
    "create")
        create_pod
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|remove|build|status|logs|create}"
        echo
        echo "Commands:"
        echo "  start   - Create pod and start both containers"
        echo "  stop    - Stop the pod"
        echo "  restart - Restart the pod"
        echo "  remove  - Remove the pod and containers"
        echo "  build   - Build container images"
        echo "  status  - Show pod and container status"
        echo "  logs    - Show container logs (usage: logs <main|userbot> [lines])"
        echo "  create  - Create pod only"
        echo
        echo "Examples:"
        echo "  $0 build        # Build images"
        echo "  $0 start        # Start the pod"
        echo "  $0 logs main    # Show main bot logs"
        echo "  $0 logs userbot 100  # Show last 100 userbot logs"
        echo "  $0 status       # Show status"
        exit 1
        ;;
esac