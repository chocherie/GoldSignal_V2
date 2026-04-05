# Push GoldSignal_V2 to GitHub

Local git is initialized on `main` with an initial commit (+ chore to drop Excel lock files).

## Automated (create repo + push)

From the repo root, with a [classic PAT](https://github.com/settings/tokens) (**repo** scope):

```bash
export GITHUB_TOKEN="ghp_xxxxxxxx"   # never commit this
./scripts/create_github_repo_and_push.sh chocherie
```

This project’s GitHub user is **chocherie** → **`https://github.com/chocherie/GoldSignal_V2`**. Optional second argument changes the repo name (default `GoldSignal_V2`).

## Manual: Create the empty repo on GitHub

1. Open [github.com/new](https://github.com/new).
2. **Repository name:** `GoldSignal_V2` (or rename locally if you prefer another name).
3. Choose **Public** or **Private**.
4. **Do not** add a README, `.gitignore`, or license (this tree already has them).
5. Create the repository.

## 2. Point `origin` at GitHub and push

```bash
cd "/path/to/Gold Dashboard V2"
git remote set-url origin https://github.com/chocherie/GoldSignal_V2.git
git push -u origin main
```

SSH (if you use keys):

```bash
git remote set-url origin git@github.com:chocherie/GoldSignal_V2.git
git push -u origin main
```

If Git prompts for credentials, use a [Personal Access Token](https://github.com/settings/tokens) as the password for HTTPS, or install the [GitHub CLI](https://cli.github.com/) and run `gh auth login`.

## Current local remote

Expected: `origin` → `https://github.com/chocherie/GoldSignal_V2.git` (`git remote -v`).
