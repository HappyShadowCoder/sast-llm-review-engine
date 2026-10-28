import pytest
from pathlib import Path
from src.dataset_builder import generate_sample_datasets


@pytest.fixture(scope="session")
def sample_data_dir(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("ml_data")
    sft_file, dpo_file = generate_sample_datasets(tmp_dir)
    return {
        "dir": tmp_dir,
        "sft_file": sft_file,
        "dpo_file": dpo_file,
    }
