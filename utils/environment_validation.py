import importlib.metadata  
import subprocess
import os
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import parse as parse_version


# --- Constants ---
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_ENV_PATH = os.path.join(MODULE_DIR, "environments/base.txt")

# It's good practice to handle potential FileNotFoundError here
try:
    BASE_ENV = Path(BASE_ENV_PATH).open().read().strip().split("\n")
except FileNotFoundError:
    print(f"Warning: Base environment file not found at {BASE_ENV_PATH}")
    BASE_ENV = []


def validate_libraries(libraries):
    """
    Validates if the specified libraries are installed and meet version requirements.

    This function uses `importlib.metadata` to get the list of installed packages,
    which is the modern replacement for the deprecated `pkg_resources`.

    Args:
        libraries (list[str]): A list of library requirement strings (e.g., "pandas>=1.0").

    Returns:
        tuple[list[str], list[str]]: A tuple containing two lists:
                                     - The first list has installed and compatible packages.
                                     - The second list has missing or incompatible packages.
    """
    # Create a dictionary of installed packages, mapping the normalized name to its version.
    # The name is normalized to lowercase to ensure case-insensitive matching.
    installed_packages_dict = {
        dist.metadata["Name"].lower(): dist.version
        for dist in importlib.metadata.distributions()
    }

    installed_packages_list = []
    not_installed_packages_list = []

    for lib_string in libraries:
        if not lib_string or lib_string.startswith('#'):
            continue  # Skip empty lines or comments

        # The Requirement object normalizes the package name (e.g., 'My_Package' -> 'my-package').
        req = Requirement(lib_string)
        
        # Look up the installed version using the normalized name.
        installed_version_str = installed_packages_dict.get(req.name.lower())

        if installed_version_str is None:
            # The package is not found in the environment.
            not_installed_packages_list.append(lib_string)
        else:
            # The package is installed; now check if the version is compatible.
            installed_version = parse_version(installed_version_str)
            # The `contains` method checks if the installed version satisfies the specifier.
            # We add `prereleases=True` to correctly handle pre-release versions.
            if req.specifier.contains(installed_version, prereleases=True):
                installed_packages_list.append(lib_string)
            else:
                # The installed version does not meet the version requirement.
                not_installed_packages_list.append(lib_string)

    return installed_packages_list, not_installed_packages_list


def install_libraries(libraries):
    """
    Installs a list of libraries using pip.

    Args:
        libraries (list[str]): A list of libraries to install.
    """
    for library in libraries:
        print(f"Installing {library}...")
        try:
            # Using -Uqq for upgrade, quiet, and quieter installation.
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-Uqq", library],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            print(f"Successfully installed {library}.")
        except subprocess.CalledProcessError as e:
            # Provide a more informative error message.
            print(f"Failed to install {library}. Pip process exited with error: {e}")


def validate_environment(requirements_file="requirements.txt"):
    """
    Validates the Python environment against a base set of libraries and a requirements file.
    """
    print("Validating base environment...")
    base_installed, base_not_installed = validate_libraries(BASE_ENV)
    if base_not_installed:
        print("Installing missing base libraries...")
        install_libraries(base_not_installed)
    print("Base environment validated successfully.")

    # These imports are placed here because they are only used in this function
    # and might not be installed until the base environment is validated.
    from rich import print as rprint
    from rich.console import Console

    rprint(
        "[#4cc9f0 bold]Validating lab environment from requirements.txt[/#4cc9f0 bold] :sparkles:"
    )

    try:
        requirements = Path(requirements_file).open().read().strip().split("\n")
    except FileNotFoundError:
        rprint(
            f"[#ef233c]Error: '{requirements_file}' not found. Please ensure the file exists.[/#ef233c]"
        )
        return

    installed, not_installed = validate_libraries(requirements)

    # Build and print the environment status report
    installed_msg = (
        "[#e85d04 underline bold]ENVIRONMENT STATUS[/#e85d04 underline bold]\n"
    )
    for pkg in installed:
        installed_msg += f":white_check_mark: [green]{pkg} is installed[/green]\n"
    for pkg in not_installed:
        installed_msg += f":x: [#ef233c]{pkg} is not installed or has wrong version[/#ef233c]\n"
    rprint(installed_msg)

    if not_installed:
        rprint("[cyan bold]Installing/updating missing libraries...[/cyan bold]")
        install_libraries(not_installed)
        rprint("[#a7c957]Installation complete![/#a7c957]")

    rprint(
        "[#a7c957]All required libraries are installed. :tada:\nYou may proceed with the lab! :rocket:[/#a7c957]"
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
    """
    Validates access to a list of required AWS Bedrock models.
    """
    from rich import print as rprint

    validation_msg = (
        "[#e85d04 underline bold]MODEL ACCESS STATUS[/#e85d04 underline bold]\n"
    )
    all_models_accessible = True
    for model in required_models:
        status = _model_access(model)
        if status:
            validation_msg += (
                f":white_check_mark: [green]{model} is accessible[/green]\n"
            )
        else:
            validation_msg += f":x: [#ef233c]{model} is not accessible[/#ef233c]\n"
            all_models_accessible = False
            
    rprint(validation_msg)

    if all_models_accessible:
        rprint(
            "[#a7c957]All required models are accessible. :tada:\nYou may proceed with the lab! :rocket:[/#a7c957]"
        )
    else:
        rprint(
            "[#ef233c]One or more models are not accessible. Please enable access in the AWS Console as explained in the workshop instructions.[/#ef233c]"
        )

