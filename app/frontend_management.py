import logging
import re
import sys
import importlib
from typing import Dict, Optional
from aiohttp import web
from importlib.metadata import version

from utils.install_util import get_missing_requirements_message, get_required_packages_versions

import app.logger


def frontend_install_warning_message():
    return f"""
{get_missing_requirements_message()}

The ComfyUI frontend is shipped in a pip package so it needs to be updated separately from the ComfyUI code.
""".strip()

def parse_version(version: str) -> tuple[int, int, int]:
        return tuple(map(int, version.split(".")))

def is_valid_version(version: str) -> bool:
    """Validate if a string is a valid semantic version (X.Y.Z format)."""
    pattern = r"^(\d+)\.(\d+)\.(\d+)$"
    return bool(re.match(pattern, version))

def get_required_frontend_version():
    return get_required_packages_versions().get("comfyui-frontend-package", None)


COMFY_PACKAGE_VERSIONS = []
def get_comfy_package_versions():
    """List installed/required versions for every comfy* package in requirements.txt."""
    if COMFY_PACKAGE_VERSIONS:
        return COMFY_PACKAGE_VERSIONS.copy()
    out = COMFY_PACKAGE_VERSIONS
    for name, required in (get_required_packages_versions() or {}).items():
        if not name.startswith("comfy"):
            continue
        try:
            installed = version(name)
        except Exception:
            installed = None
        out.append({"name": name, "installed": installed, "required": required})
    return out.copy()


def check_comfy_packages_versions():
    """Warn for every comfy* package whose installed version is below requirements.txt."""
    from packaging.version import InvalidVersion, parse as parse_pep440
    outdated_packages = []

    for pkg in get_comfy_package_versions():
        installed_str = pkg["installed"]
        required_str = pkg["required"]
        if not installed_str or not required_str:
            continue
        try:
            outdated = parse_pep440(installed_str) < parse_pep440(required_str)
        except InvalidVersion as e:
            logging.error(f"Failed to check {pkg['name']} version: {e}")
            continue
        if outdated:
            outdated_packages.append((pkg["name"], installed_str, required_str))
        else:
            logging.info("{} version: {}".format(pkg["name"], installed_str))

    if outdated_packages:
        package_warnings = "\n".join(
            f"Installed {name} version {installed} is lower than the recommended version {required}."
            for name, installed, required in outdated_packages
        )
        app.logger.log_startup_warning(
            f"""
________________________________________________________________________
WARNING WARNING WARNING WARNING WARNING

{package_warnings}

{get_missing_requirements_message()}
________________________________________________________________________
""".strip()
        )


class FrontendManager:
    @classmethod
    def get_required_frontend_version(cls) -> str:
        """Get the required frontend package version."""
        return get_required_frontend_version()

    @classmethod
    def get_installed_templates_version(cls) -> str:
        """Get the currently installed workflow templates package version."""
        try:
            templates_version_str = version("comfyui-workflow-templates")
            return templates_version_str
        except Exception:
            return None

    @classmethod
    def get_required_templates_version(cls) -> str:
        return get_required_packages_versions().get("comfyui-workflow-templates", None)

    @classmethod
    def get_comfy_package_versions(cls):
        """List installed/required versions for every comfy* package in requirements.txt."""
        return get_comfy_package_versions()

    @classmethod
    def default_frontend_path(cls) -> str:
        try:
            import comfyui_frontend_package

            return str(importlib.resources.files(comfyui_frontend_package) / "static")
        except ImportError:
            logging.error(
                f"""
********** ERROR ***********

comfyui-frontend-package is not installed.

{frontend_install_warning_message()}

********** ERROR ***********
""".strip()
            )
            sys.exit(-1)

    @classmethod
    def template_asset_map(cls) -> Optional[Dict[str, str]]:
        """Return a mapping of template asset names to their absolute paths."""
        try:
            from comfyui_workflow_templates import (
                get_asset_path,
                iter_templates,
            )
        except ImportError:
            logging.error(
                f"""
********** ERROR ***********

comfyui-workflow-templates is not installed.

{frontend_install_warning_message()}

********** ERROR ***********
""".strip()
            )
            return None

        try:
            template_entries = list(iter_templates())
        except Exception as exc:
            logging.error(f"Failed to enumerate workflow templates: {exc}")
            return None

        asset_map: Dict[str, str] = {}
        for entry in template_entries:
            for asset in entry.assets:
                try:
                    asset_map[asset.filename] = get_asset_path(
                        entry.template_id, asset.filename
                    )
                except FileNotFoundError:
                    continue
                except Exception as exc:
                    logging.error(f"Failed to resolve template asset paths: {exc}")
                    return None

        if not asset_map:
            logging.error("No workflow template assets found. Did the packages install correctly?")
            return None

        return asset_map


    @classmethod
    def legacy_templates_path(cls) -> Optional[str]:
        """Return the legacy templates directory shipped inside the meta package."""
        try:
            import comfyui_workflow_templates

            return str(
                importlib.resources.files(comfyui_workflow_templates) / "templates"
            )
        except ImportError:
            logging.error(
                f"""
********** ERROR ***********

comfyui-workflow-templates is not installed.

{frontend_install_warning_message()}

********** ERROR ***********
""".strip()
            )
            return None

    @classmethod
    def embedded_docs_path(cls) -> str:
        """Get the path to embedded documentation"""
        try:
            import comfyui_embedded_docs

            return str(
                importlib.resources.files(comfyui_embedded_docs) / "docs"
            )
        except ImportError:
            logging.info("comfyui-embedded-docs package not found")
            return None

    @classmethod
    def init_frontend(cls) -> str:
        """Return the path of the frontend shipped in the installed comfyui-frontend-package."""
        check_comfy_packages_versions()
        return cls.default_frontend_path()

    @classmethod
    def template_asset_handler(cls):
        assets = cls.template_asset_map()
        if not assets:
            return None

        async def serve_template(request: web.Request) -> web.StreamResponse:
            rel_path = request.match_info.get("path", "")
            target = assets.get(rel_path)
            if target is None:
                raise web.HTTPNotFound()
            return web.FileResponse(target)

        return serve_template
