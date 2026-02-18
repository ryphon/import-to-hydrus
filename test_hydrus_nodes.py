import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import torch
from PIL import Image
from tempfile import TemporaryFile
import json
import hashlib

from hydrus_node import HydrusImport, HydrusExport, HydrusDuplicates


class TestHydrusImport:
    
    @patch('hydrus_node.get_hydrus_client')
    def test_init(self, mock_get_client, mock_hydrus_client):
        """Test HydrusImport initialization"""
        mock_get_client.return_value = mock_hydrus_client
        hydrus_import = HydrusImport()
        # The class doesn't store client as an attribute, just calls get_hydrus_client when needed
        assert hydrus_import is not None
    
    def test_input_types(self):
        """Test INPUT_TYPES class method"""
        input_types = HydrusImport.INPUT_TYPES()
        
        assert "required" in input_types
        assert "optional" in input_types
        assert "hidden" in input_types
        
        assert "images" in input_types["required"]
        assert "positive" in input_types["optional"]
        assert "negative" in input_types["optional"]
        assert "tags" in input_types["optional"]
        assert input_types["optional"]["tags"][1]["default"] == "ai, comfyui, hyshare: ai"
    
    @patch('hydrus_node.get_hydrus_client')
    @patch('hydrus_node.hydrus_api.utils.verify_permissions')
    @patch('hydrus_node.get_hydrus_service_key')
    def test_import_image_success(self, mock_get_service_key, mock_verify_perms, mock_get_client, mock_hydrus_client):
        """Test successful image import"""
        mock_get_client.return_value = mock_hydrus_client
        mock_verify_perms.return_value = True
        mock_get_service_key.return_value = "test_service_key"
        
        hydrus_import = HydrusImport()
        
        # Mock the add_and_tag method
        hydrus_import.add_and_tag = Mock(return_value={"status": 1, "hash": "test_hash"})
        
        result = hydrus_import.import_image("fake_image_data", mock_hydrus_client, ["tag1", "tag2"])
        
        assert result == {"status": 1, "hash": "test_hash"}
        hydrus_import.add_and_tag.assert_called_once()
    
    @patch('hydrus_node.get_hydrus_client')
    @patch('hydrus_node.hydrus_api.utils.verify_permissions')
    def test_import_image_no_permissions(self, mock_verify_perms, mock_get_client, mock_hydrus_client):
        """Test image import with insufficient permissions"""
        mock_get_client.return_value = mock_hydrus_client
        mock_verify_perms.return_value = False
        
        hydrus_import = HydrusImport()
        
        with pytest.raises(PermissionError):
            hydrus_import.import_image("fake_image_data", mock_hydrus_client, ["tag1"])
    
    @patch('hydrus_node.get_hydrus_client')
    def test_add_and_tag(self, mock_get_client, mock_hydrus_client):
        """Test add_and_tag method"""
        mock_get_client.return_value = mock_hydrus_client
        mock_hydrus_client.add_file.return_value = {"status": 1, "hash": "new_hash"}
        
        hydrus_import = HydrusImport()
        result = hydrus_import.add_and_tag(mock_hydrus_client, "image_data", ["tag1", "tag2"], "service_key")
        
        mock_hydrus_client.add_file.assert_called_once_with("image_data")
        mock_hydrus_client.add_tags.assert_called_once_with(
            hashes=["new_hash"], 
            service_keys_to_tags={"service_key": ["tag1", "tag2"]}
        )
        assert result == {"status": 1, "hash": "new_hash"}


class TestHydrusExport:
    
    @patch('hydrus_node.get_hydrus_client')
    def test_init(self, mock_get_client, mock_hydrus_client):
        """Test HydrusExport initialization"""
        mock_get_client.return_value = mock_hydrus_client
        hydrus_export = HydrusExport()
        assert hydrus_export.client == mock_hydrus_client
    
    @patch('hydrus_node.folder_paths.get_input_directory')
    @patch('os.listdir')
    @patch('os.path.isfile')
    def test_input_types(self, mock_isfile, mock_listdir, mock_get_input_dir):
        """Test INPUT_TYPES class method"""
        mock_get_input_dir.return_value = "/fake/input"
        mock_listdir.return_value = ["image1.png", "image2.jpg", "subfolder"]
        mock_isfile.side_effect = lambda x: x.endswith(('.png', '.jpg'))
        
        input_types = HydrusExport.INPUT_TYPES()
        
        assert "required" in input_types
        assert "optional" in input_types
        assert "images" in input_types["optional"]
        assert "tag" in input_types["optional"]
        assert "hash" in input_types["optional"]
    
    @patch('hydrus_node.get_hydrus_client')
    def test_get_files_with_tag(self, mock_get_client, mock_hydrus_client):
        """Test getting files with specific tag"""
        mock_get_client.return_value = mock_hydrus_client
        
        hydrus_export = HydrusExport()
        hash_list = hydrus_export.get_files_with_tag("test_tag")
        
        mock_hydrus_client.search_files.assert_called_once_with(["test_tag"])
        mock_hydrus_client.get_file_metadata.assert_called_once_with(file_ids=[1, 2, 3])
        assert hash_list == ["test_hash_123"]
    
    @patch('hydrus_node.get_hydrus_client')
    @patch('hydrus_node.get_hydrus_service_key')
    def test_get_file_metadata(self, mock_get_service_key, mock_get_client, mock_hydrus_client):
        """Test getting file metadata"""
        mock_get_client.return_value = mock_hydrus_client
        mock_get_service_key.return_value = "test_service_key"
        
        hydrus_export = HydrusExport()
        metadata = hydrus_export.get_file_metadata("test_hash")
        
        expected = {
            'loras': ['test_lora'],
            'modelname': 'test_model',
            'positive': 'test positive prompt',
            'negative': 'test negative prompt',
            'seed': '12345'
        }
        assert metadata == expected
    
    @patch('hydrus_node.get_hydrus_client')
    def test_get_file(self, mock_get_client, mock_hydrus_client):
        """Test getting file content"""
        mock_get_client.return_value = mock_hydrus_client
        
        hydrus_export = HydrusExport()
        file_content = hydrus_export.get_file("test_hash")
        
        mock_hydrus_client.get_file.assert_called_once_with("test_hash")
        assert file_content == b'fake_image_data'


class TestHydrusDuplicates:
    
    def test_input_types(self):
        """Test INPUT_TYPES class method"""
        input_types = HydrusDuplicates.INPUT_TYPES()
        
        assert "required" in input_types
        assert "original_hash" in input_types["required"]
        assert "upscaled_hash" in input_types["required"]
    
    @patch('hydrus_node.get_hydrus_client')
    @patch('time.sleep')
    def test_dedupe(self, mock_sleep, mock_get_client, mock_hydrus_client):
        """Test deduplication functionality"""
        mock_get_client.return_value = mock_hydrus_client
        mock_hydrus_client.set_file_relationships.return_value = {"success": True}
        
        hydrus_duplicates = HydrusDuplicates()
        result = hydrus_duplicates.dedupe("original_hash", "upscaled_hash")
        
        expected_body = [
            {
                "hash_a": "original_hash",
                "hash_b": "upscaled_hash",
                "relationship": 4,
                "do_default_content_merge": True
            }
        ]
        
        mock_hydrus_client.set_file_relationships.assert_called_once_with(expected_body)
        assert result == {"success": True}


class TestNodeClassMappings:
    
    def test_node_class_mappings_exists(self):
        """Test that NODE_CLASS_MAPPINGS is properly defined"""
        from hydrus_node import NODE_CLASS_MAPPINGS
        
        assert "Hydrus Image Importer" in NODE_CLASS_MAPPINGS
        assert "Hydrus Image Exporter" in NODE_CLASS_MAPPINGS  
        assert "Hydrus Image Dedupe" in NODE_CLASS_MAPPINGS
        
        assert NODE_CLASS_MAPPINGS["Hydrus Image Importer"] == HydrusImport
        assert NODE_CLASS_MAPPINGS["Hydrus Image Exporter"] == HydrusExport
        assert NODE_CLASS_MAPPINGS["Hydrus Image Dedupe"] == HydrusDuplicates