"""Unit tests for the ConfluenceConfig class."""

import os
from unittest.mock import patch

import pytest

from mcp_atlassian.confluence.config import ConfluenceConfig


def test_from_env_success():
    """Test that from_env successfully creates a config from environment variables."""
    # Need to clear and reset the environment for this test
    with patch.dict(
        "os.environ",
        {
            "CONFLUENCE_URL": "https://test.atlassian.net/wiki",
            "CONFLUENCE_USERNAME": "test_username",
            "CONFLUENCE_API_TOKEN": "test_token",
        },
        clear=True,  # Clear existing environment variables
    ):
        config = ConfluenceConfig.from_env()
        assert config.url == "https://test.atlassian.net/wiki"
        assert config.username == "test_username"
        assert config.api_token == "test_token"


def test_from_env_success_rewrite():
    """Test that from_env successfully creates a config from environment variables."""
    # Need to clear and reset the environment for this test
    with patch.dict(
        "os.environ",
        {
            "CONFLUENCE_URL": "https://test.atlassian.net/wiki",
            "CONFLUENCE_USERNAME": "test_username",
            "CONFLUENCE_API_TOKEN": "test_token",
            "CONFLUENCE_PERSONAL_TOKEN": "test_personal_token",
            "CONFLUENCE_SSL_VERIFY": "true",
            "CONFLUENCE_SPACES_FILTER": "SPACE1",
        },
        clear=True,  # Clear existing environment variables
    ):
        config = ConfluenceConfig.from_env(
            {
                "CONFLUENCE_URL": "https://test.atlassian.net/anotherwiki",
                "CONFLUENCE_USERNAME": "test_username2",
                "CONFLUENCE_API_TOKEN": "test_token2",
                "CONFLUENCE_PERSONAL_TOKEN": "test_personal_token2",
                "CONFLUENCE_SSL_VERIFY": "false",
                "CONFLUENCE_SPACES_FILTER": "SPACE2",
                "ATLASSIAN_OAUTH_CLIENT_ID": "test_client_id",
                "ATLASSIAN_OAUTH_CLIENT_SECRET": "test_client_secret",
                "ATLASSIAN_OAUTH_REDIRECT_URI": "test_redirect_uri",
                "ATLASSIAN_OAUTH_SCOPE": "test_scope",
            }
        )
        assert config.url == "https://test.atlassian.net/anotherwiki"
        assert config.username == "test_username2"
        assert config.api_token == "test_token2"
        assert config.personal_token == "test_personal_token2"
        assert not config.ssl_verify
        assert config.spaces_filter == "SPACE2"
        assert config.oauth_config.client_id == "test_client_id"
        assert config.oauth_config.client_secret == "test_client_secret"


def test_from_env_missing_url():
    """Test that from_env raises ValueError when URL is missing."""
    original_env = os.environ.copy()
    try:
        os.environ.clear()
        with pytest.raises(
            ValueError, match="Missing required CONFLUENCE_URL environment variable"
        ):
            ConfluenceConfig.from_env()
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_from_env_missing_cloud_auth():
    """Test that from_env raises ValueError when cloud auth credentials are missing."""
    with patch.dict(
        os.environ,
        {
            "CONFLUENCE_URL": "https://test.atlassian.net",  # Cloud URL
        },
        clear=True,
    ):
        with pytest.raises(
            ValueError,
            match="Cloud authentication requires CONFLUENCE_USERNAME and CONFLUENCE_API_TOKEN",
        ):
            ConfluenceConfig.from_env()


def test_from_env_missing_server_auth():
    """Test that from_env raises ValueError when server auth credentials are missing."""
    with patch.dict(
        os.environ,
        {
            "CONFLUENCE_URL": "https://confluence.example.com",  # Server URL
        },
        clear=True,
    ):
        with pytest.raises(
            ValueError,
            match="Server/Data Center authentication requires CONFLUENCE_PERSONAL_TOKEN",
        ):
            ConfluenceConfig.from_env()


def test_is_cloud():
    """Test that is_cloud property returns correct value."""
    # Arrange & Act - Cloud URL
    config = ConfluenceConfig(
        url="https://example.atlassian.net/wiki",
        auth_type="basic",
        username="test",
        api_token="test",
    )

    # Assert
    assert config.is_cloud is True

    # Arrange & Act - Server URL
    config = ConfluenceConfig(
        url="https://confluence.example.com",
        auth_type="pat",
        personal_token="test",
    )

    # Assert
    assert config.is_cloud is False

    # Arrange & Act - Localhost URL (Data Center/Server)
    config = ConfluenceConfig(
        url="http://localhost:8090",
        auth_type="pat",
        personal_token="test",
    )

    # Assert
    assert config.is_cloud is False

    # Arrange & Act - IP localhost URL (Data Center/Server)
    config = ConfluenceConfig(
        url="http://127.0.0.1:8090",
        auth_type="pat",
        personal_token="test",
    )

    # Assert
    assert config.is_cloud is False


def test_from_env_proxy_settings():
    """Test that from_env correctly loads proxy environment variables."""
    with patch.dict(
        os.environ,
        {
            "CONFLUENCE_URL": "https://test.atlassian.net/wiki",
            "CONFLUENCE_USERNAME": "test_username",
            "CONFLUENCE_API_TOKEN": "test_token",
            "HTTP_PROXY": "http://proxy.example.com:8080",
            "HTTPS_PROXY": "https://proxy.example.com:8443",
            "SOCKS_PROXY": "socks5://user:pass@proxy.example.com:1080",
            "NO_PROXY": "localhost,127.0.0.1",
        },
        clear=True,
    ):
        config = ConfluenceConfig.from_env()
        assert config.http_proxy == "http://proxy.example.com:8080"
        assert config.https_proxy == "https://proxy.example.com:8443"
        assert config.socks_proxy == "socks5://user:pass@proxy.example.com:1080"
        assert config.no_proxy == "localhost,127.0.0.1"

    # Service-specific overrides
    with patch.dict(
        os.environ,
        {
            "CONFLUENCE_URL": "https://test.atlassian.net/wiki",
            "CONFLUENCE_USERNAME": "test_username",
            "CONFLUENCE_API_TOKEN": "test_token",
            "CONFLUENCE_HTTP_PROXY": "http://confluence-proxy.example.com:8080",
            "CONFLUENCE_HTTPS_PROXY": "https://confluence-proxy.example.com:8443",
            "CONFLUENCE_SOCKS_PROXY": "socks5://user:pass@confluence-proxy.example.com:1080",
            "CONFLUENCE_NO_PROXY": "localhost,127.0.0.1,.internal.example.com",
        },
        clear=True,
    ):
        config = ConfluenceConfig.from_env()
        assert config.http_proxy == "http://confluence-proxy.example.com:8080"
        assert config.https_proxy == "https://confluence-proxy.example.com:8443"
        assert (
            config.socks_proxy == "socks5://user:pass@confluence-proxy.example.com:1080"
        )
        assert config.no_proxy == "localhost,127.0.0.1,.internal.example.com"


def test_is_cloud_oauth_with_cloud_id():
    """Test that is_cloud returns True for OAuth with cloud_id regardless of URL."""
    from mcp_atlassian.utils.oauth import BYOAccessTokenOAuthConfig

    # OAuth with cloud_id and no URL - should be Cloud
    oauth_config = BYOAccessTokenOAuthConfig(
        cloud_id="test-cloud-id", access_token="test-token"
    )
    config = ConfluenceConfig(
        url=None,  # URL can be None in Multi-Cloud OAuth mode
        auth_type="oauth",
        oauth_config=oauth_config,
    )
    assert config.is_cloud is True

    # OAuth with cloud_id and server URL - should still be Cloud
    config = ConfluenceConfig(
        url="https://confluence.example.com",  # Server-like URL
        auth_type="oauth",
        oauth_config=oauth_config,
    )
    assert config.is_cloud is True


<<<<<<< HEAD
def test_from_env_oauth_enable_no_url():
    """Test BYOT OAuth mode - ATLASSIAN_OAUTH_ENABLE=true without URL or cloud_id."""
    with patch.dict(
        os.environ,
        {
            "ATLASSIAN_OAUTH_ENABLE": "true",
            # No CONFLUENCE_URL set
            # No ATLASSIAN_OAUTH_CLOUD_ID set
        },
        clear=True,
    ):
        config = ConfluenceConfig.from_env()
        assert config.auth_type == "oauth"
        assert config.is_cloud is False


def test_from_env_oauth_enable_no_url_with_cloud_id():
    """Test BYOT OAuth mode - ATLASSIAN_OAUTH_ENABLE=true without URL but with cloud_id."""
    with patch.dict(
        os.environ,
        {
            "ATLASSIAN_OAUTH_ENABLE": "true",
            "ATLASSIAN_OAUTH_CLOUD_ID": "test-cloud-id",
            # No CONFLUENCE_URL set
        },
        clear=True,
    ):
        config = ConfluenceConfig.from_env()
        assert config.auth_type == "oauth"
        assert config.is_cloud is True


def test_from_env_oauth_enable_with_cloud_url():
    """Test BYOT OAuth mode - ATLASSIAN_OAUTH_ENABLE=true with Cloud URL."""
    with patch.dict(
        os.environ,
        {
            "ATLASSIAN_OAUTH_ENABLE": "true",
            "CONFLUENCE_URL": "https://test.atlassian.net/wiki",
        },
        clear=True,
    ):
        config = ConfluenceConfig.from_env()
        assert config.url == "https://test.atlassian.net/wiki"
        assert config.auth_type == "oauth"
        assert config.is_cloud is True  # Should be Cloud based on URL


def test_from_env_oauth_enable_with_server_url():
    """Test BYOT OAuth mode - ATLASSIAN_OAUTH_ENABLE=true with Server URL."""
    with patch.dict(
        os.environ,
        {
            "ATLASSIAN_OAUTH_ENABLE": "true",
            "CONFLUENCE_URL": "https://confluence.example.com",
=======
def test_from_env_with_client_cert():
    """Test loading config with client certificate settings from environment."""
    with patch.dict(
        "os.environ",
        {
            "CONFLUENCE_URL": "https://confluence.example.com",
            "CONFLUENCE_USERNAME": "test_user",
            "CONFLUENCE_API_TOKEN": "test_token",
            "CONFLUENCE_CLIENT_CERT": "/path/to/cert.pem",
            "CONFLUENCE_CLIENT_KEY": "/path/to/key.pem",
            "CONFLUENCE_CLIENT_KEY_PASSWORD": "secret",
>>>>>>> feature/client-certificate-auth
        },
        clear=True,
    ):
        config = ConfluenceConfig.from_env()
<<<<<<< HEAD
        assert config.url == "https://confluence.example.com"
        assert config.auth_type == "oauth"
        assert config.is_cloud is False  # Should be Server based on URL
=======

        assert config.url == "https://confluence.example.com"
        assert config.client_cert == "/path/to/cert.pem"
        assert config.client_key == "/path/to/key.pem"
        assert config.client_key_password == "secret"


def test_from_env_without_client_cert():
    """Test loading config without client certificate settings."""
    with patch.dict(
        "os.environ",
        {
            "CONFLUENCE_URL": "https://confluence.example.com",
            "CONFLUENCE_USERNAME": "test_user",
            "CONFLUENCE_API_TOKEN": "test_token",
        },
        clear=True,
    ):
        config = ConfluenceConfig.from_env()

        assert config.url == "https://confluence.example.com"
        assert config.client_cert is None
        assert config.client_key is None
        assert config.client_key_password is None
>>>>>>> feature/client-certificate-auth
