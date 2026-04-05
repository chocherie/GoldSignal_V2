# Push GoldSignal_V2 to GitHub

Local git is initialized on `main` with an initial commit (+ chore to drop Excel lock files).

## 1. Create the empty repo on GitHub

1. Open [github.com/new](https://github.com/new).
2. **Repository name:** `GoldSignal_V2` (or rename locally if you prefer another name).
3. Choose **Public** or **Private**.
4. **Do not** add a README, `.gitignore`, or license (this tree already has them).
5. Create the repository.

## 2. Point `origin` at *your* account and push

Replace `YOUR_GITHUB_USERNAME` with your real GitHub username or org:

```bash
cd "/path/to/Gold Dashboard V2"
git remote set-url origin https://github.com/YOUR_GITHUB_USERNAME/GoldSignal_V2.git
git push -u origin main
```

SSH (if you use keys):

```bash
git remote set-url origin git@github.com:YOUR_GITHUB_USERNAME/GoldSignal_V2.git
git push -u origin main
```

If Git prompts for credentials, use a [Personal Access Token](https://github.com/settings/tokens) as the password for HTTPS, or install the [GitHub CLI](https://cli.github.com/) and run `gh auth login`.

## Current local remote (adjust if wrong)

After setup, `git remote -v` should show your URL. If it still references another user, run `git remote set-url` as above.
