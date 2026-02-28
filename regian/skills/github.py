import os
from github import Github, GithubException
from dotenv import load_dotenv

load_dotenv()

def _get_github_client():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN niet gevonden in .env bestand.")
    return Github(token)

def _get_repo(repo_name: str):
    g = _get_github_client()
    user = g.get_user()
    return user.get_repo(repo_name)

# ── REPOSITORIES ────────────────────────────────────────────

def repo_create(name: str, private: bool = True) -> str:
    """
    Maakt een nieuwe GitHub repository aan. Geef 'name' op en optioneel 'private' (standaard True).
    """
    try:
        g = _get_github_client()
        user = g.get_user()
        repo = user.create_repo(name, private=private)
        return f"Succes: Repository '{name}' aangemaakt op {repo.html_url}"
    except Exception as e:
        return f"Fout bij aanmaken repo: {str(e)}"

def repo_list() -> str:
    """
    Toont alle GitHub repositories van de ingelogde gebruiker.
    """
    try:
        g = _get_github_client()
        user = g.get_user()
        repos = [f"{'🔒' if r.private else '🌐'} {r.name} — {r.html_url}" for r in user.get_repos()]
        return "\n".join(repos) if repos else "Geen repositories gevonden."
    except Exception as e:
        return f"Fout bij ophalen repos: {str(e)}"

def repo_info(repo_name: str) -> str:
    """
    Toont details van een specifieke repository. Geef 'repo_name' op.
    """
    try:
        repo = _get_repo(repo_name)
        return (
            f"**{repo.full_name}**\n"
            f"- Beschrijving: {repo.description or 'geen'}\n"
            f"- Zichtbaarheid: {'Privé' if repo.private else 'Publiek'}\n"
            f"- Standaard branch: {repo.default_branch}\n"
            f"- Sterren: {repo.stargazers_count}\n"
            f"- URL: {repo.html_url}"
        )
    except Exception as e:
        return f"Fout bij ophalen repo info: {str(e)}"

def repo_delete(repo_name: str) -> str:
    """
    Verwijdert een GitHub repository permanent. Geef 'repo_name' op.
    """
    try:
        repo = _get_repo(repo_name)
        repo.delete()
        return f"Succes: Repository '{repo_name}' verwijderd."
    except Exception as e:
        return f"Fout bij verwijderen repo: {str(e)}"

# ── BESTANDEN ────────────────────────────────────────────────

def commit_and_push(repo_name: str, file_path: str, commit_message: str) -> str:
    """
    Commit en pusht een lokaal bestand naar een GitHub repository. Geef 'repo_name', 'file_path' en 'commit_message' op.
    file_path is relatief aan de geconfigureerde root directory (REGIAN_ROOT_DIR).
    """
    try:
        from regian.settings import get_root_dir
        import os as _os
        # Oplossen relatief aan root dir, tenzij al absoluut
        resolved = file_path if _os.path.isabs(file_path) else _os.path.join(get_root_dir(), file_path)
        repo = _get_repo(repo_name)
        with open(resolved, 'r', encoding='utf-8') as f:
            content = f.read()
        # Gebruik alleen de bestandsnaam als pad in de repo
        repo_path = _os.path.basename(file_path)
        try:
            existing = repo.get_contents(repo_path)
            repo.update_file(existing.path, commit_message, content, existing.sha)
            return f"Succes: '{repo_path}' geüpdatet in '{repo_name}'"
        except GithubException:
            repo.create_file(repo_path, commit_message, content)
            return f"Succes: '{repo_path}' aangemaakt in '{repo_name}'"
    except Exception as e:
        return f"Fout bij GitHub push: {str(e)}"

def file_list(repo_name: str, path: str = "") -> str:
    """
    Toont de bestanden en mappen in een GitHub repository. Geef 'repo_name' op en optioneel 'path'.
    """
    try:
        repo = _get_repo(repo_name)
        contents = repo.get_contents(path)
        items = [f"{'📁' if c.type == 'dir' else '📄'} {c.path}" for c in contents]
        return "\n".join(items) if items else "Lege map."
    except Exception as e:
        return f"Fout bij ophalen bestanden: {str(e)}"

def file_read(repo_name: str, file_path: str) -> str:
    """
    Leest de inhoud van een bestand in een GitHub repository. Geef 'repo_name' en 'file_path' op.
    """
    try:
        repo = _get_repo(repo_name)
        content = repo.get_contents(file_path)
        return content.decoded_content.decode("utf-8")
    except Exception as e:
        return f"Fout bij lezen bestand: {str(e)}"

# ── BRANCHES ─────────────────────────────────────────────────

def branch_list(repo_name: str) -> str:
    """
    Toont alle branches van een GitHub repository. Geef 'repo_name' op.
    """
    try:
        repo = _get_repo(repo_name)
        branches = [b.name for b in repo.get_branches()]
        return "\n".join(branches) if branches else "Geen branches gevonden."
    except Exception as e:
        return f"Fout bij ophalen branches: {str(e)}"

def branch_create(repo_name: str, branch_name: str, from_branch: str = "") -> str:
    """
    Maakt een nieuwe branch aan in een GitHub repository. Geef 'repo_name', 'branch_name' en optioneel 'from_branch' op.
    """
    try:
        repo = _get_repo(repo_name)
        source = from_branch or repo.default_branch
        sha = repo.get_branch(source).commit.sha
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=sha)
        return f"Succes: Branch '{branch_name}' aangemaakt vanuit '{source}'."
    except Exception as e:
        return f"Fout bij aanmaken branch: {str(e)}"

# ── ISSUES ────────────────────────────────────────────────────

def issue_create(repo_name: str, title: str, body: str = "") -> str:
    """
    Maakt een nieuw issue aan in een GitHub repository. Geef 'repo_name', 'title' en optioneel 'body' op.
    """
    try:
        repo = _get_repo(repo_name)
        issue = repo.create_issue(title=title, body=body)
        return f"Succes: Issue #{issue.number} aangemaakt: {issue.html_url}"
    except Exception as e:
        return f"Fout bij aanmaken issue: {str(e)}"

def issue_list(repo_name: str, state: str = "open") -> str:
    """
    Toont issues van een GitHub repository. Geef 'repo_name' op en optioneel 'state' (open/closed/all).
    """
    try:
        repo = _get_repo(repo_name)
        issues = repo.get_issues(state=state)
        result = [f"#{i.number} [{i.state}] {i.title} — {i.html_url}" for i in issues]
        return "\n".join(result) if result else f"Geen {state} issues gevonden."
    except Exception as e:
        return f"Fout bij ophalen issues: {str(e)}"

def issue_close(repo_name: str, issue_number: int) -> str:
    """
    Sluit een issue in een GitHub repository. Geef 'repo_name' en 'issue_number' op.
    """
    try:
        repo = _get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        issue.edit(state="closed")
        return f"Succes: Issue #{issue_number} gesloten."
    except Exception as e:
        return f"Fout bij sluiten issue: {str(e)}"

# ── PULL REQUESTS ─────────────────────────────────────────────

def pull_request_create(repo_name: str, title: str, head: str, base: str = "", body: str = "") -> str:
    """
    Maakt een pull request aan. Geef 'repo_name', 'title', 'head' branch en optioneel 'base' branch en 'body' op.
    """
    try:
        repo = _get_repo(repo_name)
        target = base or repo.default_branch
        pr = repo.create_pull(title=title, body=body, head=head, base=target)
        return f"Succes: Pull Request #{pr.number} aangemaakt: {pr.html_url}"
    except Exception as e:
        return f"Fout bij aanmaken pull request: {str(e)}"

def pull_request_list(repo_name: str, state: str = "open") -> str:
    """
    Toont pull requests van een GitHub repository. Geef 'repo_name' op en optioneel 'state' (open/closed/all).
    """
    try:
        repo = _get_repo(repo_name)
        prs = repo.get_pulls(state=state)
        result = [f"#{pr.number} [{pr.state}] {pr.title} ({pr.head.ref} → {pr.base.ref}) — {pr.html_url}" for pr in prs]
        return "\n".join(result) if result else f"Geen {state} pull requests gevonden."
    except Exception as e:
        return f"Fout bij ophalen pull requests: {str(e)}"
