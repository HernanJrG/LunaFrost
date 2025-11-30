#!/bin/bash

# Configuration
BACKUP_DIR="/var/www/translator/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
echo "Backing up PostgreSQL..."
PGPASSWORD="a2DzQLUIsowfyB" pg_dump -U translator -h localhost translator_db > "$BACKUP_DIR/db_$DATE.sql"
gzip "$BACKUP_DIR/db_$DATE.sql"

# Backup user data (images, exports, user files)
echo "Backing up user data..."
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" -C /var/www/translator data/

# Backup environment and config
echo "Backing up configuration..."
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" /var/www/translator/.env /etc/cloudflared/config.yml

# Delete old backups
echo "Cleaning old backups..."
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $DATE"
