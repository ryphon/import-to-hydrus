import pytest
import json
import os
import sys
from unittest.mock import Mock, patch, mock_open
import responses


def get_files_with_tag(tag, client):
    """Copy of function from submit.py for testing"""
    hash_list = []
    file_ids = client.search_files([tag])['file_ids']
    files_metadata = client.get_file_metadata(file_ids=file_ids)['metadata']
    for individual_file in files_metadata:
        hash_list.append(individual_file['hash'])
    return hash_list

def queue_prompt(prompt):
    """Copy of function from submit.py for testing"""
    import requests
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    resp = requests.post("http://10.0.0.4:8188/prompt", data=data)
    print(resp.text)


class TestSubmitScript:
    
    def test_get_files_with_tag(self):
        """Test getting files with specific tag from Hydrus"""
        mock_client = Mock()
        mock_client.search_files.return_value = {'file_ids': [1, 2, 3]}
        mock_client.get_file_metadata.return_value = {
            'metadata': [
                {'hash': 'hash1'},
                {'hash': 'hash2'},
                {'hash': 'hash3'}
            ]
        }
        
        result = get_files_with_tag("test_tag", mock_client)
        
        mock_client.search_files.assert_called_once_with(["test_tag"])
        mock_client.get_file_metadata.assert_called_once_with(file_ids=[1, 2, 3])
        assert result == ['hash1', 'hash2', 'hash3']
    
    def test_get_files_with_tag_empty_result(self):
        """Test getting files when no files have the tag"""
        mock_client = Mock()
        mock_client.search_files.return_value = {'file_ids': []}
        mock_client.get_file_metadata.return_value = {'metadata': []}
        
        result = get_files_with_tag("nonexistent_tag", mock_client)
        
        assert result == []
    
    @responses.activate
    def test_queue_prompt_success(self):
        """Test successful prompt queuing to ComfyUI"""
        # Mock the ComfyUI API response
        responses.add(
            responses.POST,
            "http://10.0.0.4:8188/prompt",
            json={"prompt_id": "test_prompt_id"},
            status=200
        )
        
        test_prompt = {"test": "prompt_data"}
        
        # Capture print output
        with patch('builtins.print') as mock_print:
            queue_prompt(test_prompt)
        
        # Verify the request was made
        assert len(responses.calls) == 1
        request_data = json.loads(responses.calls[0].request.body)
        assert request_data == {"prompt": test_prompt}
        
        # Verify print was called with response
        mock_print.assert_called_once()
    
    @responses.activate
    def test_queue_prompt_error(self):
        """Test prompt queuing with API error"""
        # Mock an error response
        responses.add(
            responses.POST,
            "http://10.0.0.4:8188/prompt",
            json={"error": "Invalid prompt"},
            status=400
        )
        
        test_prompt = {"invalid": "prompt"}
        
        with patch('builtins.print') as mock_print:
            queue_prompt(test_prompt)
        
        # Verify the request was made
        assert len(responses.calls) == 1
        mock_print.assert_called_once()


class TestSubmitScriptIntegration:
    
    @patch('test_submit.queue_prompt')
    @patch('test_submit.get_files_with_tag')
    @patch('builtins.open', mock_open(read_data='{"59": {"inputs": {}}}'))
    def test_script_execution_flow(self, mock_get_files, mock_queue_prompt):
        """Test the main script execution flow"""
        # Mock client and file retrieval
        mock_client = Mock()
        mock_get_files.return_value = ['hash1', 'hash2']
        
        # Simulate the main script logic
        with open("upscale_workflow.json", "r") as file:
            prompt = json.loads(file.read())
        
        tag = "tobeupscaledbeta" 
        hash_list = mock_get_files(tag, mock_client)
        
        for i in hash_list:
            prompt['59']['inputs']['hash'] = i
            mock_queue_prompt(prompt)
        
        # Verify the calls
        assert mock_queue_prompt.call_count == 2  # Called for each hash
        mock_get_files.assert_called_once_with("tobeupscaledbeta", mock_client)