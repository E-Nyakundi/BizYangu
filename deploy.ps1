<#
  deploy.ps1
  ----------
  BizYangu git-based deploy. Replaces the old tar -> scp -> --overwrite
  flow. Run this from the project root (same folder as docker-compose.prod.yml)
  after your local git repo + GitHub remote + VM deploy key are already
  set up (see VM_GIT_DEPLOY_SETUP.md).

  What it does:
    1. Commits any local changes (git add -A + commit).
    2. Pushes to origin/main.
    3. SSHes into the VM, does `git pull`, rebuilds and restarts the
       Docker Compose stack.

  Usage:
      .\deploy.ps1 -Message "fix: settle_payment MESSAGES keys"

  First time, edit the four defaults below (or pass them as -params
  every time) so they match your actual VM.
#>

param(
    [string]$Message = "Deploy",
    [string]$VMHost = "YOUR_VM_IP_OR_HOSTNAME",
    [string]$VMUser = "ubuntu",
    [string]$RemotePath = "~/BizYangu",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

function Section($text) {
    Write-Host ""
    Write-Host "== $text ==" -ForegroundColor Cyan
}

# ---------------------------------------------------------------------
# 1. Local commit
# ---------------------------------------------------------------------
Section "1. Committing local changes"

git add -A
$statusOutput = git status --porcelain

if ($statusOutput) {
    git commit -m "$Message"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "git commit failed — aborting deploy." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "No local changes to commit — deploying current HEAD." -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------
# 2. Push
# ---------------------------------------------------------------------
Section "2. Pushing to origin/$Branch"

git push origin $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Host "git push failed — aborting deploy. Nothing was touched on the VM." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------
# 3. Pull + rebuild on the VM
# ---------------------------------------------------------------------
Section "3. Pulling + rebuilding on the VM ($VMUser@$VMHost)"

# NOTE: intentionally no `docker compose exec backend python manage.py
# migrate` here — Dockerfile.prod already runs `migrate --noinput` on
# every container start. Running it again here can race the container's
# own auto-migrate on a cold start.
$remoteCmd = @"
set -e
cd $RemotePath
echo '--- git status before pull ---'
git status --short
echo '--- pulling ---'
git pull origin $Branch
echo '--- rebuilding + restarting stack ---'
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
echo '--- done, recent backend logs ---'
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=20 backend
"@

ssh "$VMUser@$VMHost" $remoteCmd
if ($LASTEXITCODE -ne 0) {
    Write-Host "Remote deploy step failed. Local push already succeeded — SSH in manually to check." -ForegroundColor Red
    exit 1
}

Section "Done"
Write-Host "Tail logs any time with:" -ForegroundColor Green
Write-Host "  ssh $VMUser@$VMHost `"docker compose -f $RemotePath/docker-compose.prod.yml logs -f backend`""
