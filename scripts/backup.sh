#!/bin/bash

# AI Knowledge Base Backup Script
# This script creates backups of the database and file storage

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ENVIRONMENT="development"
KEEP_DAYS=7

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
    echo "  -d, --dir DIRECTORY      Backup directory [default: ./backups]"
    echo "  -k, --keep DAYS          Keep backups for N days [default: 7]"
    echo "  --db-only               Backup database only"
    echo "  --files-only            Backup files only"
    echo "  --restore FILE          Restore from backup file"
    echo "  --list                  List available backups"
    echo "  --cleanup               Clean old backups"
    echo "  -h, --help              Show this help message"
}

# Function to create backup directory
create_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        print_status "Creating backup directory: $BACKUP_DIR"
        mkdir -p "$BACKUP_DIR"
    fi
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

# Function to backup database
backup_database() {
    print_status "Backing up PostgreSQL database..."
    
    local container_name=$(get_container_name "postgres")
    local backup_file="$BACKUP_DIR/postgres_${TIMESTAMP}.sql"
    
    # Check if container is running
    if ! docker ps --format "table {{.Names}}" | grep -q "$container_name"; then
        print_error "PostgreSQL container not running: $container_name"
        return 1
    fi
    
    # Create database backup
    docker exec "$container_name" pg_dump -U postgres -d ai_knowledge_base > "$backup_file"
    
    # Compress the backup
    gzip "$backup_file"
    backup_file="${backup_file}.gz"
    
    local size=$(du -h "$backup_file" | cut -f1)
    print_success "Database backup created: $backup_file ($size)"
}

# Function to backup MinIO files
backup_files() {
    print_status "Backing up MinIO files..."
    
    local container_name=$(get_container_name "minio")
    local backup_file="$BACKUP_DIR/minio_${TIMESTAMP}.tar.gz"
    
    # Check if container is running
    if ! docker ps --format "table {{.Names}}" | grep -q "$container_name"; then
        print_error "MinIO container not running: $container_name"
        return 1
    fi
    
    # Create files backup
    docker run --rm \
        --volumes-from "$container_name" \
        -v "$PWD/$BACKUP_DIR:/backup" \
        alpine:latest \
        tar czf "/backup/minio_${TIMESTAMP}.tar.gz" -C /data .
    
    local size=$(du -h "$backup_file" | cut -f1)
    print_success "Files backup created: $backup_file ($size)"
}

# Function to backup Qdrant vector database
backup_qdrant() {
    print_status "Backing up Qdrant vector database..."
    
    local container_name=$(get_container_name "qdrant")
    local backup_file="$BACKUP_DIR/qdrant_${TIMESTAMP}.tar.gz"
    
    # Check if container is running
    if ! docker ps --format "table {{.Names}}" | grep -q "$container_name"; then
        print_error "Qdrant container not running: $container_name"
        return 1
    fi
    
    # Create Qdrant backup
    docker run --rm \
        --volumes-from "$container_name" \
        -v "$PWD/$BACKUP_DIR:/backup" \
        alpine:latest \
        tar czf "/backup/qdrant_${TIMESTAMP}.tar.gz" -C /qdrant/storage .
    
    local size=$(du -h "$backup_file" | cut -f1)
    print_success "Qdrant backup created: $backup_file ($size)"
}

# Function to create full backup
create_full_backup() {
    print_status "Creating full backup..."
    
    create_backup_dir
    
    local success=true
    
    if [ "$FILES_ONLY" != "true" ]; then
        backup_database || success=false
        backup_qdrant || success=false
    fi
    
    if [ "$DB_ONLY" != "true" ]; then
        backup_files || success=false
    fi
    
    if [ "$success" = "true" ]; then
        print_success "Full backup completed successfully"
        
        # Create backup manifest
        cat > "$BACKUP_DIR/backup_${TIMESTAMP}.manifest" << EOF
Backup Manifest
===============
Timestamp: $(date)
Environment: $ENVIRONMENT
Files:
$(ls -la "$BACKUP_DIR"/*_${TIMESTAMP}.* 2>/dev/null || echo "No files found")
EOF
        
    else
        print_error "Backup completed with errors"
        return 1
    fi
}

# Function to restore from backup
restore_backup() {
    local backup_file=$1
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        return 1
    fi
    
    print_warning "This will restore data and may overwrite existing data!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Restore cancelled"
        return 0
    fi
    
    print_status "Restoring from backup: $backup_file"
    
    # Determine backup type from filename
    if [[ "$backup_file" == *"postgres"* ]]; then
        restore_database "$backup_file"
    elif [[ "$backup_file" == *"minio"* ]]; then
        restore_files "$backup_file"
    elif [[ "$backup_file" == *"qdrant"* ]]; then
        restore_qdrant "$backup_file"
    else
        print_error "Unknown backup file type"
        return 1
    fi
}

# Function to restore database
restore_database() {
    local backup_file=$1
    local container_name=$(get_container_name "postgres")
    
    print_status "Restoring PostgreSQL database..."
    
    # Decompress if needed
    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" | docker exec -i "$container_name" psql -U postgres -d ai_knowledge_base
    else
        docker exec -i "$container_name" psql -U postgres -d ai_knowledge_base < "$backup_file"
    fi
    
    print_success "Database restored successfully"
}

# Function to restore files
restore_files() {
    local backup_file=$1
    local container_name=$(get_container_name "minio")
    
    print_status "Restoring MinIO files..."
    
    docker run --rm \
        --volumes-from "$container_name" \
        -v "$PWD/$backup_file:/backup.tar.gz" \
        alpine:latest \
        sh -c "cd /data && tar xzf /backup.tar.gz"
    
    print_success "Files restored successfully"
}

# Function to restore Qdrant
restore_qdrant() {
    local backup_file=$1
    local container_name=$(get_container_name "qdrant")
    
    print_status "Restoring Qdrant vector database..."
    
    docker run --rm \
        --volumes-from "$container_name" \
        -v "$PWD/$backup_file:/backup.tar.gz" \
        alpine:latest \
        sh -c "cd /qdrant/storage && tar xzf /backup.tar.gz"
    
    print_success "Qdrant restored successfully"
}

# Function to list backups
list_backups() {
    print_status "Available backups in $BACKUP_DIR:"
    
    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "Backup directory does not exist: $BACKUP_DIR"
        return 0
    fi
    
    echo ""
    echo "Database backups:"
    ls -lh "$BACKUP_DIR"/postgres_*.sql.gz 2>/dev/null || echo "  No database backups found"
    
    echo ""
    echo "File backups:"
    ls -lh "$BACKUP_DIR"/minio_*.tar.gz 2>/dev/null || echo "  No file backups found"
    
    echo ""
    echo "Vector database backups:"
    ls -lh "$BACKUP_DIR"/qdrant_*.tar.gz 2>/dev/null || echo "  No vector database backups found"
    
    echo ""
    echo "Manifests:"
    ls -lh "$BACKUP_DIR"/*.manifest 2>/dev/null || echo "  No manifests found"
}

# Function to cleanup old backups
cleanup_backups() {
    print_status "Cleaning up backups older than $KEEP_DAYS days..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "Backup directory does not exist: $BACKUP_DIR"
        return 0
    fi
    
    local deleted=0
    
    # Find and delete old backups
    while IFS= read -r -d '' file; do
        rm "$file"
        print_status "Deleted: $(basename "$file")"
        ((deleted++))
    done < <(find "$BACKUP_DIR" -name "*.sql.gz" -o -name "*.tar.gz" -o -name "*.manifest" -type f -mtime +$KEEP_DAYS -print0)
    
    if [ $deleted -eq 0 ]; then
        print_status "No old backups to clean up"
    else
        print_success "Cleaned up $deleted old backup files"
    fi
}

# Parse command line arguments
DB_ONLY="false"
FILES_ONLY="false"
ACTION="backup"
RESTORE_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -d|--dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        -k|--keep)
            KEEP_DAYS="$2"
            shift 2
            ;;
        --db-only)
            DB_ONLY="true"
            shift
            ;;
        --files-only)
            FILES_ONLY="true"
            shift
            ;;
        --restore)
            ACTION="restore"
            RESTORE_FILE="$2"
            shift 2
            ;;
        --list)
            ACTION="list"
            shift
            ;;
        --cleanup)
            ACTION="cleanup"
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
print_status "AI Knowledge Base Backup Script"
print_status "Environment: $ENVIRONMENT"
print_status "Backup Directory: $BACKUP_DIR"

case $ACTION in
    "backup")
        create_full_backup
        ;;
    "restore")
        restore_backup "$RESTORE_FILE"
        ;;
    "list")
        list_backups
        ;;
    "cleanup")
        cleanup_backups
        ;;
esac

print_success "Operation completed!"