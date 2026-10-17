from types import SimpleNamespace
from unittest.mock import patch, mock_open

import pytest

from app.frontend_management import FrontendManager


@pytest.fixture(autouse=True)
def clear_cache():
    import utils.install_util
    import app.frontend_management

    utils.install_util.PACKAGE_VERSIONS = {}
    app.frontend_management.COMFY_PACKAGE_VERSIONS = []


def test_init_frontend_default_with_mocks():
    with (
        patch("app.frontend_management.check_comfy_packages_versions") as mock_check,
        patch.object(
            FrontendManager, "default_frontend_path", return_value="/mocked/path"
        ),
    ):
        frontend_path = FrontendManager.init_frontend()

    # Assert
    assert frontend_path == "/mocked/path"
    mock_check.assert_called_once()


def test_get_frontend_version():
    # Arrange
    expected_version = "1.25.0"
    mock_requirements_content = """torch
torchsde
comfyui-frontend-package==1.25.0
other-package==1.0.0
numpy"""

    # Act
    with patch("builtins.open", mock_open(read_data=mock_requirements_content)):
        version = FrontendManager.get_required_frontend_version()

    # Assert
    assert version == expected_version


def test_get_frontend_version_invalid_semver():
    # Arrange
    mock_requirements_content = """torch
torchsde
comfyui-frontend-package==1.29.3.75
other-package==1.0.0
numpy"""

    # Act
    with patch("builtins.open", mock_open(read_data=mock_requirements_content)):
        version = FrontendManager.get_required_frontend_version()

    # Assert
    assert version is None


def test_get_templates_version():
    # Arrange
    expected_version = "0.1.41"
    mock_requirements_content = """torch
torchsde
comfyui-frontend-package==1.25.0
comfyui-workflow-templates==0.1.41
other-package==1.0.0
numpy"""

    # Act
    with patch("builtins.open", mock_open(read_data=mock_requirements_content)):
        version = FrontendManager.get_required_templates_version()

    # Assert
    assert version == expected_version


def test_get_templates_version_not_found():
    # Arrange
    mock_requirements_content = """torch
torchsde
comfyui-frontend-package==1.25.0
other-package==1.0.0
numpy"""

    # Act
    with patch("builtins.open", mock_open(read_data=mock_requirements_content)):
        version = FrontendManager.get_required_templates_version()

    # Assert
    assert version is None


def test_get_templates_version_invalid_semver():
    # Arrange
    mock_requirements_content = """torch
torchsde
comfyui-workflow-templates==1.0.0.beta
other-package==1.0.0
numpy"""

    # Act
    with patch("builtins.open", mock_open(read_data=mock_requirements_content)):
        version = FrontendManager.get_required_templates_version()

    # Assert
    assert version is None


def test_get_installed_templates_version():
    # Arrange
    expected_version = "0.1.40"

    # Act
    with patch("app.frontend_management.version", return_value=expected_version):
        version = FrontendManager.get_installed_templates_version()

    # Assert
    assert version == expected_version


def test_get_installed_templates_version_not_installed():
    # Act
    with patch(
        "app.frontend_management.version", side_effect=Exception("Package not found")
    ):
        version = FrontendManager.get_installed_templates_version()

    # Assert
    assert version is None


def test_template_asset_map_skips_missing_assets():
    template_entries = [
        SimpleNamespace(
            template_id="example",
            assets=[
                SimpleNamespace(filename="example.json"),
                SimpleNamespace(filename="preview.webp"),
            ],
        )
    ]

    def get_asset_path(template_id, filename):
        if filename == "preview.webp":
            raise FileNotFoundError
        return f"/templates/{filename}"

    with (
        patch(
            "comfyui_workflow_templates.iter_templates",
            return_value=template_entries,
        ),
        patch(
            "comfyui_workflow_templates.get_asset_path",
            side_effect=get_asset_path,
        ),
    ):
        asset_map = FrontendManager.template_asset_map()

    assert asset_map == {"example.json": "/templates/example.json"}
