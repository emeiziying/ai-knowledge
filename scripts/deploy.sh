#!/bin/bash

# AI Knowledge Base Deployment Script
# This script helps deploy the application in different environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="development"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --env ENVIRONMENT    Set environment (development|production) [default: development]"
    echo "  -f, --file FILE         Docker compose file to use"
    echo "  --env-file FILE         Environment file to use [default: .env]"
    echo "  --build                 Force rebuild of images"
    echo "  --pull                  Pull latest images before starting"
    echo "  --logs                  Show logs after deployment"
    echo "  --stop                  Stop all services"
    echo "  --down                  Stop and remove all containers"
    echo "  --clean                 Remove all containers, networks, and volumes"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy in development mode"
    echo "  $0 -e production                     # Deploy in production mode"
    echo "  $0 --build --pull                    # Force rebuild and pull latest images"
    echo "  $0 --stop                            # Stop all services"
    echo "  $0 --down                            # Stop and remove containers"
    echo "  $0 --clean                           # Complete cleanup"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to setup environment
setup_environment() {
    print_status "Setting up environment for: $ENVIRONMENT"
    
    # Set compose file based on environment
    if [ "$ENVIRONMENT" = "production" ]; then
        COMPOSE_FILE="docker-compose.prod.yml"
        if [ "$ENV_FILE" = ".env" ]; then
            ENV_FILE=".env.prod"
        fi
    elif [ "$ENVIRONMENT" = "development" ]; then
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    # Check if compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    # Check if environment file exists
    if [ ! -f "$ENV_FILE" ]; then
        print_warning "Environment file not found: $ENV_FILE"
        if [ -f ".env.example" ]; then
            print_status "Copying .env.example to $ENV_FILE"
            cp .env.example "$ENV_FILE"
            print_warning "Please edit $ENV_FILE with your configuration before running again"
            exit 1
        else
            print_error "No environment file found and no .env.example to copy from"
            exit 1
        fi
    fi
    
    export COMPOSE_FILE
    export ENV_FILE
}

# Function to build and start services
deploy_services() {
    local build_flag=""
    local pull_flag=""
    
    if [ "$BUILD" = "true" ]; then
        build_flag="--build"
    fi
    
    if [ "$PULL" = "true" ]; then
        pull_flag="--pull"
        print_status "Pulling latest images..."
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull
    fi
    
    print_status "Starting services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d $build_flag
    
    print_success "Services started successfully"
    
    # Wait for services to be healthy
    print_status "Waiting for services to be healthy..."
    sleep 10
    
    # Check service health
    check_service_health
}

# Function to check service health
check_service_health() {
    print_status "Checking service health..."
    
    local services=("postgres" "redis" "qdrant" "minio" "backend")
    
    for service in "${services[@]}"; do
        local container_name
        if [ "$ENVIRONMENT" = "production" ]; then
            container_name="ai_kb_${service}_prod"
        else
            container_name="ai_kb_${service}"
        fi
        
        if docker ps --format "table {{.Names}}" | grep -q "$container_name"; then
            local health=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "no-health-check")
            if [ "$health" = "healthy" ] || [ "$health" = "no-health-check" ]; then
                print_success "$service is running"
            else
                print_warning "$service is not healthy (status: $health)"
            fi
        else
            print_error "$service container not found"
        fi
    done
}

# Function to stop services
stop_services() {
    print_status "Stopping services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop
    print_success "Services stopped"
}

# Function to remove containers
down_services() {
    print_status "Stopping and removing containers..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    print_success "Containers removed"
}

# Function to clean everything
clean_all() {
    print_warning "This will remove all containers, networks, and volumes!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cleaning up everything..."
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v --remove-orphans
        print_success "Cleanup completed"
    else
        print_status "Cleanup cancelled"
    fi
}

# Function to show logs
show_logs() {
    print_status "Showing logs..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f
}

# Parse command line arguments
BUILD="false"
PULL="false"
LOGS="false"
ACTION="deploy"

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -f|--file)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --build)
            BUILD="true"
            shift
            ;;
        --pull)
            PULL="true"
            shift
            ;;
        --logs)
            LOGS="true"
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        --down)
            ACTION="down"
            shift
            ;;
        --clean)
            ACTION="clean"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate environment
if [ "$ENVIRONMENT" != "development" ] && [ "$ENVIRONMENT" != "production" ]; then
    print_error "Invalid environment: $ENVIRONMENT. Must be 'development' or 'production'"
    exit 1
fi

# Main execution
print_status "AI Knowledge Base Deployment Script"
print_status "Environment: $ENVIRONMENT"

check_prerequisites
setup_environment

case $ACTION in
    "deploy")
        deploy_services
        if [ "$LOGS" = "true" ]; then
            show_logs
        fi
        ;;
    "stop")
        stop_services
        ;;
    "down")
        down_services
        ;;
    "clean")
        clean_all
        ;;
esac

print_success "Operation completed successfully!"