import pkg_resources
import importlib
import pkg_resources
import subprocess
import os
import sys

from packaging.requirements import Requirement
from packaging.version import parse as parse_version

from pathlib import Path


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_ENV_PATH = os.path.join(MODULE_DIR, "environments/base.txt")

BASE_ENV = Path(BASE_ENV_PATH).open().read().strip().split("\n")


def validate_libraries(libraries):
    importlib.reload(pkg_resources)
    installed_packages = pkg_resources.working_set
    installed_packages_dict = {i.key: i.version for i in installed_packages}

    installed_packages_list = []
    not_installed_packages_list = []

    for lib in libraries:
        if "_" in lib:
            lib = lib.replace("_", "-")
        lib = lib.lower()
        req = Requirement(lib)
        installed_version = installed_packages_dict.get(req.name)

        if installed_version is None:
            not_installed_packages_list.append(lib)
        else:
            installed_version = parse_version(installed_version)
            if req.specifier.contains(installed_version):
                installed_packages_list.append(lib)
            else:
                not_installed_packages_list.append(lib)

    return installed_packages_list, not_installed_packages_list


def install_libraries(libraries):

    for library in libraries:

        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-Uqq", library],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            print(f"{library} has been installed successfully.")
        except subprocess.CalledProcessError as e:
            return f"Failed to install {library}. Error: {str(e)}"


def validate_environment():

    print("Validating base environment")
    base_installed, base_not_installed = validate_libraries(BASE_ENV)
    install_libraries(base_not_installed)
    print("Base environment validated successfully")

    from rich import print as rprint
    from rich.console import Console

    rprint(
        "[#4cc9f0 bold]Validating lab environment from requirements.txt[/#4cc9f0 bold] :sparkles:"
    )

    try:
        requirements = Path("requirements.txt").open().read().strip().split("\n")
    except FileNotFoundError:
        rprint(
            "[#ef233c]requirements.txt file not found. Please make sure the file exists in the current directory.[/#ef233c]"
        )
        return

    installed, not_installed = validate_libraries(requirements)

    installed_msg = (
        "[#e85d04 underline bold]ENVIRONMENT STATUS[/#e85d04 underline bold]\n"
    )

    for pkg in installed:
        installed_msg += f":white_check_mark: [green] {pkg} is installed[/green]\n"

    for pkg in not_installed:
        installed_msg += f":x: [#ef233c]{pkg} is not installed[/#ef233c]\n"
    rprint(installed_msg)

    if len(not_installed) > 0:
        rprint("[cyan bold]Installing missing libraries[/cyan bold]")
        install_libraries(not_installed)

    rprint(
        "[#a7c957]All required libraries are installed.:tada:\nYou may proceed with the lab! :rocket:[/#a7c957]"
    )


def _model_access(model_id):

    import boto3

    session = boto3.Session()
    bedrock_runtime = session.client("bedrock-runtime")

    try:
        bedrock_runtime.invoke_model(modelId=model_id, body="{}")
    except Exception as e:
        if "AccessDeniedException" in str(e):
            return False
        else:
            return True


def validate_model_access(required_models):
    from rich import print as rprint

    validation_msg = (
        "[#e85d04 underline bold]MODEL ACCESS STATUS[/#e85d04 underline bold]\n"
    )
    for model in required_models:
        status = _model_access(model)
        if status:
            validation_msg += (
                f":white_check_mark: [green] {model} is accessible[/green]\n"
            )
        else:
            validation_msg += f":x: [#ef233c]{model} is not accessible[/#ef233c]\n"
    rprint(validation_msg)

    if all([_model_access(model) for model in required_models]):
        rprint(
            "[#a7c957]All required models are accessible.:tada:\nYou may proceed with the lab! :rocket:[/#a7c957]"
        )
    else:
        rprint(
            "[#ef233c]Please enable access to the model in the AWS Console as explained in the workshop instructions[/#ef233c]"
        )
