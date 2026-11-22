# Push the gold/ folder of the workspace repo to github.com/terachaiy/thai-gold-dashboard (main).
# Commit your changes in the workspace first. Authors are rewritten to the GitHub no-reply address
# so no personal e-mail becomes public. The workspace is the source of truth: main is replaced.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
  if (-not (git remote | Select-String -Quiet '^gold-gh$')) {
    git remote add gold-gh https://github.com/terachaiy/thai-gold-dashboard.git
  }
  git subtree split --prefix=gold -b gold-publish | Out-Null
  git branch -f gold-publish-public gold-publish
  $env:FILTER_BRANCH_SQUELCH_WARNING = '1'
  git filter-branch -f --env-filter @'
export GIT_AUTHOR_NAME=terachaiy GIT_AUTHOR_EMAIL=terachaiy@users.noreply.github.com
export GIT_COMMITTER_NAME=terachaiy GIT_COMMITTER_EMAIL=terachaiy@users.noreply.github.com
'@ gold-publish-public | Out-Null
  git push --force gold-gh gold-publish-public:refs/heads/main
} finally { Pop-Location }
