from huggingface_hub import snapshot_download
from pathlib import Path
import shutil


def download_model(model_name, local_model_path, revision=None, ignore_patterns=None):

    local_model_path = Path(local_model_path)

    if local_model_path.exists():

        print(f"Model already exists at {local_model_path}\nSkipping download")

        return local_model_path

    local_model_path = Path(local_model_path)
    local_model_path.mkdir(exist_ok=True, parents=True)
    local_cache_path = Path("./tmp_cache")
    snapshot_download(
        repo_id=model_name,
        local_dir_use_symlinks=False,
        revision=revision,
        cache_dir=local_cache_path,
        local_dir=local_model_path,
        ignore_patterns=ignore_patterns,
    )
    shutil.rmtree(local_cache_path)

    return local_model_path