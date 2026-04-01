"""System Prompt API統合テスト。"""


def test_get_system_prompt_creates_from_template(test_client, tmp_path, monkeypatch):
    """テンプレートから自動生成される。"""

    context_dir = tmp_path / "context"
    template_dir = context_dir / "templates"
    template_dir.mkdir(parents=True)
    (template_dir / "USER.md").write_text("template", encoding="utf-8")

    monkeypatch.setattr(
        "backend.infrastructure.context_files.get_context_dir",
        lambda: context_dir,
    )

    response = test_client.get(
        "/v1/system-prompts/user",
        headers={"X-API-Key": "test-backend-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "user"
    assert data["content"] == "template"
    assert (context_dir / "USER.md").read_text(encoding="utf-8") == "template"


def test_update_system_prompt_persists_content(test_client, tmp_path, monkeypatch):
    """PUTでファイル内容が更新される。"""

    context_dir = tmp_path / "context"
    context_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "backend.infrastructure.context_files.get_context_dir",
        lambda: context_dir,
    )

    response = test_client.put(
        "/v1/system-prompts/user",
        headers={"X-API-Key": "test-backend-key"},
        json={"content": "updated"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "user"
    assert data["content"] == "updated"
    assert (context_dir / "USER.md").read_text(encoding="utf-8") == "updated"


def test_system_prompt_requires_api_key(test_client):
    """APIキーが必須。"""

    response = test_client.get("/v1/system-prompts/user")

    assert response.status_code == 401


def test_system_prompt_rejects_invalid_name(test_client):
    """未知のキーは400を返す。"""

    response = test_client.get(
        "/v1/system-prompts/unknown",
        headers={"X-API-Key": "test-backend-key"},
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("invalid_name")
