import pytest
import os
import sys
from unittest.mock import Mock, MagicMock, patch
import numpy as np
import torch
from PIL import Image

# Mock ComfyUI modules before any imports
mock_comfy = MagicMock()
mock_comfy.sd = MagicMock()
mock_folder_paths = MagicMock()
mock_folder_paths.get_input_directory.return_value = "/fake/input"
mock_folder_paths.get_full_path.return_value = "/fake/checkpoint.safetensors"
mock_folder_paths.get_annotated_filepath.return_value = "/fake/image.png"

sys.modules['comfy'] = mock_comfy
sys.modules['comfy.sd'] = mock_comfy.sd  
sys.modules['folder_paths'] = mock_folder_paths


@pytest.fixture
def mock_hydrus_client():
    """Mock Hydrus API client for testing"""
    client = Mock()
    client.get_services.return_value = {
        'local_tags': [{'name': 'my tags', 'service_key': 'test_service_key'}]
    }
    client.search_files.return_value = {'file_ids': [1, 2, 3]}
    client.get_file_metadata.return_value = {
        'metadata': [
            {
                'hash': 'test_hash_123',
                'tags': {
                    'test_service_key': {
                        'display_tags': {
                            '0': [
                                'modelname:test_model',
                                'positive:test positive prompt',
                                'negative:test negative prompt',
                                'seed:12345',
                                'lora:test_lora'
                            ]
                        }
                    }
                }
            }
        ]
    }
    client.get_file.return_value = Mock(content=b'fake_image_data')
    client.add_file.return_value = {'status': 1, 'hash': 'new_hash_456'}
    client.add_tags.return_value = True
    client.set_file_relationships.return_value = True
    return client


@pytest.fixture
def sample_image_tensor():
    """Create a sample image tensor for testing"""
    # Create a 64x64 RGB image tensor
    image_array = np.random.rand(64, 64, 3).astype(np.float32)
    return torch.from_numpy(image_array)[None,]


@pytest.fixture
def sample_pil_image():
    """Create a sample PIL image for testing"""
    return Image.new('RGB', (64, 64), color='red')


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing"""
    monkeypatch.setenv("HYDRUS_KEY", "test_api_key")
    monkeypatch.setenv("HYDRUS_URL", "http://localhost:45869")


@pytest.fixture
def mock_comfy_modules(mocker):
    """Mock ComfyUI modules that might not be available during testing"""
    mocker.patch('comfy.sd')
    mocker.patch('folder_paths')
    return True