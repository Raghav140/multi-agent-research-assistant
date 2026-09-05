#!/bin/bash
# SQLite Database Backup Script for Multi-Agent Research Assistant
# This script backs up research_memory.db and evaluation_metrics.db from Docker volumes

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESEARCH_DB_SOURCE="/app/data/research_memory.db"
METRICS_DB_SOURCE="/app/data/evaluation_metrics.db"
RESEARCH_DB_BACKUP="$BACKUP_DIR/research_memory_$TIMESTAMP.db"
METRICS_DB_BACKUP="$BACKUP_DIR/evaluation_metrics_$TIMESTAMP.db"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check if running in Docker
if [ ! -f "/.dockerenv" ]; then
    print_error "This script must be run inside the backend container"
    print_info "Run with: docker exec multi-agent-backend /scripts/backup_sqlite.sh"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"
print_success "Backup directory: $BACKUP_DIR"

# Backup research_memory.db using SQLite online backup
print_info "Backing up research_memory.db..."
if [ -f "$RESEARCH_DB_SOURCE" ]; then
    sqlite3 "$RESEARCH_DB_SOURCE" ".backup '$RESEARCH_DB_BACKUP'"
    print_success "Research memory backup: $RESEARCH_DB_BACKUP"
else
    print_error "Research memory database not found: $RESEARCH_DB_SOURCE"
fi

# Backup evaluation_metrics.db using SQLite online backup
print_info "Backing up evaluation_metrics.db..."
if [ -f "$METRICS_DB_SOURCE" ]; then
    sqlite3 "$METRICS_DB_SOURCE" ".backup '$METRICS_DB_BACKUP'"
    print_success "Metrics backup: $METRICS_DB_BACKUP"
else
    print_error "Metrics database not found: $METRICS_DB_SOURCE"
fi

# Clean up old backups
print_info "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "research_memory_*.db" -type f -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "evaluation_metrics_*.db" -type f -mtime +$RETENTION_DAYS -delete
print_success "Old backups cleaned up"

# Print summary
print_success "Backup completed successfully"
print_info "Backup location: $BACKUP_DIR"
print_info "Retention period: $RETENTION_DAYS days"
