#!/bin/bash

# AI Knowledge Base Health Check Script
# This script checks the health of all services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="development"
TIMEOUT=30
VERBOSE=false

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
    echo "  -t, --timeout SECONDS    Health check timeout [default: 30]"
    echo "  -v, --verbose           Verbose output"
    echo "  --json                  Output in JSON format"
    echo "  -h, --help              Show this help message"
}

# Function to get container name
get_container_name() {
    local service=$1
    if [ "$ENVIRONMENT" = "production" ]; then
        echo "ai_kb_${service}_prod"
    else
        echo "ai_kb_${service}"
    fi
}

# Function to check if container is running
check_container_running() {
    local container_name=$1
    if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
        return 0
    else
        return 1
    fi
}

# Function to check container health
check_container_health() {
    local container_name=$1
    local health=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "no-health-check")
    echo "$health"
}

# Function to check service endpoint
check_endpoint() {
    local url=$1
    local timeout=${2:-$TIMEOUT}
    
    if command -v curl &> /dev/null; then
        curl -f -s --max-time "$timeout" "$url" > /dev/null 2>&1
    elif command -v wget &> /dev/null; then
        wget -q --timeout="$timeout" --tries=1 "$url" -O /dev/null 2>&1
    else
        print_error "Neither curl nor wget is available for endpoint checks"
        return 1
    fi
}

# Function to check PostgreSQL
check_postgres() {
    local container_name=$(get_container_name "postgres")
    local status="unknown"
    local details=""
    
    if check_container_running "$container_name"; then
        local health=$(check_container_health "$container_name")
        if [ "$health" = "healthy" ] || [ "$health" = "no-health-check" ]; then
            # Test database connection
            if docker exec "$container_name" pg_isready -U postgres -d ai_knowledge_base &>/dev/null; then
                status="healthy"
                details="Database connection successful"
            else
                status="unhealthy"
                details="Database connection failed"
            fi
        else
            status="unhealthy"
            details="Container health check failed: $health"
        fi
    else
        status="stopped"
        details="Container not running"
    fi
    
    echo "$status|$details"
}

# Function to check Redis
check_redis() {
    local container_name=$(get_container_name "redis")
    local status="unknown"
    local details=""
    
    if check_container_running "$container_name"; then
        local health=$(check_container_health "$container_name")
        if [ "$health" = "healthy" ] || [ "$health" = "no-health-check" ]; then
            # Test Redis connection
            if docker exec "$container_name" redis-cli ping &>/dev/null; then
                status="healthy"
                details="Redis connection successful"
            else
                status="unhealthy"
                details="Redis connection failed"
            fi
        else
            status="unhealthy"
            details="Container health check failed: $health"
        fi
    else
        status="stopped"
        details="Container not running"
    fi
    
    echo "$status|$details"
}

# Function to check Qdrant
check_qdrant() {
    local container_name=$(get_container_name "qdrant")
    local status="unknown"
    local details=""
    
    if check_container_running "$container_name"; then
        # Test Qdrant API
        if check_endpoint "http://localhost:6333/health" 10; then
            status="healthy"
            details="Qdrant API responding"
        else
            status="unhealthy"
            details="Qdrant API not responding"
        fi
    else
        status="stopped"
        details="Container not running"
    fi
    
    echo "$status|$details"
}

# Function to check MinIO
check_minio() {
    local container_name=$(get_container_name "minio")
    local status="unknown"
    local details=""
    
    if check_container_running "$container_name"; then
        # Test MinIO health endpoint
        if check_endpoint "http://localhost:9000/minio/health/live" 10; then
            status="healthy"
            details="MinIO API responding"
        else
            status="unhealthy"
            details="MinIO API not responding"
        fi
    else
        status="stopped"
        details="Container not running"
    fi
    
    echo "$status|$details"
}

# Function to check Backend
check_backend() {
    local container_name=$(get_container_name "backend")
    local status="unknown"
    local details=""
    
    if check_container_running "$container_name"; then
        # Test backend health endpoint
        if check_endpoint "http://localhost:8000/health" 15; then
            status="healthy"
            details="Backend API responding"
        else
            status="unhealthy"
            details="Backend API not responding"
        fi
    else
        status="stopped"
        details="Container not running"
    fi
    
    echo "$status|$details"
}

# Function to check Frontend
check_frontend() {
    local container_name=$(get_container_name "frontend")
    local status="unknown"
    local details=""
    
    if check_container_running "$container_name"; then
        # Test frontend
        if check_endpoint "http://localhost:3000/" 10; then
            status="healthy"
            details="Frontend responding"
        else
            status="unhealthy"
            details="Frontend not responding"
        fi
    else
        status="stopped"
        details="Container not running"
    fi
    
    echo "$status|$details"
}

# Function to check Ollama (optional)
check_ollama() {
    local container_name=$(get_container_name "ollama")
    local status="unknown"
    local details=""
    
    if check_container_running "$container_name"; then
        # Test Ollama API
        if check_endpoint "http://localhost:11434/api/tags" 10; then
            status="healthy"
            details="Ollama API responding"
        else
            status="unhealthy"
            details="Ollama API not responding"
        fi
    else
        status="not_running"
        details="Container not running (optional service)"
    fi
    
    echo "$status|$details"
}

# Function to perform comprehensive health check
perform_health_check() {
    local overall_status="healthy"
    local services=("postgres" "redis" "qdrant" "minio" "backend" "frontend")
    local optional_services=("ollama")
    
    declare -A results
    
    print_status "Performing health check for environment: $ENVIRONMENT"
    echo ""
    
    # Check core services
    for service in "${services[@]}"; do
        print_status "Checking $service..."
        local result=$(check_$service)
        local status=$(echo "$result" | cut -d'|' -f1)
        local details=$(echo "$result" | cut -d'|' -f2)
        
        results[$service]="$status|$details"
        
        case $status in
            "healthy")
                print_success "$service: $details"
                ;;
            "unhealthy"|"stopped")
                print_error "$service: $details"
                overall_status="unhealthy"
                ;;
            *)
                print_warning "$service: $details"
                ;;
        esac
        
        if [ "$VERBOSE" = "true" ]; then
            local container_name=$(get_container_name "$service")
            if check_container_running "$container_name"; then
                echo "  Container: $container_name"
                echo "  Status: $(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null || echo "unknown")"
                echo "  Uptime: $(docker inspect --format='{{.State.StartedAt}}' "$container_name" 2>/dev/null || echo "unknown")"
            fi
            echo ""
        fi
    done
    
    # Check optional services
    for service in "${optional_services[@]}"; do
        print_status "Checking $service (optional)..."
        local result=$(check_$service)
        local status=$(echo "$result" | cut -d'|' -f1)
        local details=$(echo "$result" | cut -d'|' -f2)
        
        results[$service]="$status|$details"
        
        case $status in
            "healthy")
                print_success "$service: $details"
                ;;
            "not_running")
                print_warning "$service: $details"
                ;;
            "unhealthy")
                print_warning "$service: $details (optional service)"
                ;;
            *)
                print_warning "$service: $details"
                ;;
        esac
    done
    
    echo ""
    echo "=================================="
    if [ "$overall_status" = "healthy" ]; then
        print_success "Overall system status: HEALTHY"
        exit 0
    else
        print_error "Overall system status: UNHEALTHY"
        exit 1
    fi
}

# Function to output JSON format
output_json() {
    local services=("postgres" "redis" "qdrant" "minio" "backend" "frontend" "ollama")
    
    echo "{"
    echo "  \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\","
    echo "  \"environment\": \"$ENVIRONMENT\","
    echo "  \"services\": {"
    
    local first=true
    for service in "${services[@]}"; do
        if [ "$first" = "false" ]; then
            echo ","
        fi
        first=false
        
        local result=$(check_$service)
        local status=$(echo "$result" | cut -d'|' -f1)
        local details=$(echo "$result" | cut -d'|' -f2)
        
        echo -n "    \"$service\": {"
        echo -n "\"status\": \"$status\", "
        echo -n "\"details\": \"$details\""
        echo -n "}"
    done
    
    echo ""
    echo "  }"
    echo "}"
}

# Parse command line arguments
JSON_OUTPUT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --json)
            JSON_OUTPUT=true
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
if [ "$JSON_OUTPUT" = "true" ]; then
    output_json
else
    perform_health_check
fi