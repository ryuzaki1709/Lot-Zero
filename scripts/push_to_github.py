"""Helper script to push Lot Zero repository to GitHub using Dulwich."""

import sys
from pathlib import Path
from dulwich import porcelain
from dulwich.repo import Repo

ROOT = Path(__file__).resolve().parent.parent


def push_repo(remote_url: str, token: str = None):
    repo = Repo(str(ROOT))
    repo.refs[b"refs/heads/main"] = repo.head()
    print(f"Pushing HEAD ({repo.head().decode()[:10]}) to {remote_url}...")
    
    auth_kwargs = {}
    if token:
        # If token provided, authenticate over HTTPS
        if remote_url.startswith("https://"):
            # Format url with token if needed or pass credentials
            clean_url = remote_url.replace("https://", f"https://oauth2:{token}@")
            porcelain.push(repo, clean_url, refspecs=[b"refs/heads/main:refs/heads/main"])
            print("Successfully pushed to GitHub!")
            return

    porcelain.push(repo, remote_url, refspecs=[b"refs/heads/main:refs/heads/main"])
    print("Successfully pushed to GitHub!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python push_to_github.py <GITHUB_REPO_URL> [GITHUB_TOKEN]")
        print("Example: python push_to_github.py https://github.com/saisujanreddy/lot-zero.git <TOKEN>")
        sys.exit(1)
    
    url = sys.argv[1]
    tok = sys.argv[2] if len(sys.argv) > 2 else None
    push_repo(url, tok)
