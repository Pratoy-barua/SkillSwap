$ErrorActionPreference = "Stop"

Write-Host "Starting database backup..."

$backupPath = ".\database\skillswap_data.sql"

docker compose exec -T db sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" skillswap' > $backupPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "Database backup FAILED." -ForegroundColor Red
    exit 1
}

Write-Host "Database backup completed successfully!" -ForegroundColor Green
Write-Host "Backup file: $backupPath"