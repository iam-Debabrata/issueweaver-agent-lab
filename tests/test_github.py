import io
import zipfile

import httpx
import pytest

from issueweaver.github import GitHubGateway


def make_zip(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for filename, content in files.items():
            archive.writestr("repo-abc/" + filename, content)
    return stream.getvalue()


@pytest.mark.asyncio
async def test_snapshot_and_publish_mock_github(tmp_path):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, request.content))
        name = request.url.path
        if name.endswith("issues/7"):
            data = {"number": 7, "title": "Add feature", "body": "feature"}
        elif name.endswith("/branches/main"):
            data = {"commit": {"sha": "base-sha"}}
        elif name.endswith("/git/commits/base-sha"):
            data = {"tree": {"sha": "tree-sha"}}
        elif name.endswith("/git/blobs"):
            data = {"sha": "blob-sha"}
        elif name.endswith("/git/trees"):
            data = {"sha": "new-tree"}
        elif name.endswith("/git/commits"):
            data = {"sha": "new-commit"}
        elif name.endswith("/git/refs"):
            data = {"ref": "created"}
        elif name.endswith("/pulls"):
            data = {"html_url": "https://github.com/a/b/pull/99"}
        elif name.endswith("/zipball/base-sha"):
            return httpx.Response(200, content=make_zip({"src/main.py": "x = 1\n"}))
        else:
            data = {"default_branch": "main"}
        return httpx.Response(200, json=data)

    async with httpx.AsyncClient(base_url="https://api.github.com", transport=httpx.MockTransport(handler)) as client:
        gateway = GitHubGateway("a/b", "fake-secret", client)
        issue = await gateway.get_issue(7)
        assert issue["title"] == "Add feature"
        branch, sha = await gateway.base()
        assert (branch, sha) == ("main", "base-sha")
        await gateway.checkout_archive(tmp_path, sha)
        assert (tmp_path / "src/main.py").read_text() == "x = 1\n"
        url = await gateway.create_pr(7, "Add feature", branch, sha,
            {"src/feature.py": "x = 2\n"}, run_summary="tests green")
        assert url.endswith("/99")
        assert any(path.endswith("/pulls") for _, path, _ in calls)
        assert any(b'"draft":true' in payload for _, path, payload in calls if path.endswith("/pulls"))
        await gateway.close()


@pytest.mark.asyncio
async def test_archive_path_traversal_and_oversize(tmp_path):
    for files in ({"../bad.py": "x=1"}, {"large.py": "x" * 30_000_001}):
        archive = make_zip(files)
        async with httpx.AsyncClient(base_url="https://api.github.com", transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=archive)
        )) as client:
            gateway = GitHubGateway("a/b", "token", client)
            with pytest.raises(ValueError):
                await gateway.checkout_archive(tmp_path, "main")


@pytest.mark.asyncio
async def test_invalid_publish_path_and_repo():
    with pytest.raises(ValueError):
        GitHubGateway("/not-a-repo", "token")
    with pytest.raises(ValueError):
        GitHubGateway("owner/repo", "")
    async with httpx.AsyncClient() as client:
        gateway = GitHubGateway("owner/repo", "token", client)
        with pytest.raises(ValueError):
            await gateway.create_pr(1, "title", "main", "sha", {".github/workflow.py": "x"}, run_summary="")
        with pytest.raises(ValueError):
            await gateway.get_issue(0)
