"""
Unit tests for AlphaFold API client.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
sys.path.insert(0, '/Users/lijing/literature_agent-V2-claude/protein_evaluator')

from src.alphafold_client import (
    AlphaFoldAPIClient,
    AlphaFoldModel,
    get_alphafold_model
)
from utils.exceptions import AlphaFoldAPIError


class TestAlphaFoldModel:
    """Tests for AlphaFoldModel dataclass."""
    
    def test_model_creation(self):
        """Test creating AlphaFoldModel instance."""
        model = AlphaFoldModel(
            uniprot_id="P12345",
            model_version="v4",
            plddt_score=85.5,
            sequence_length=300
        )
        
        assert model.uniprot_id == "P12345"
        assert model.model_version == "v4"
        assert model.plddt_score == 85.5
        assert model.sequence_length == 300
    
    def test_confidence_category_very_high(self):
        """Test confidence category for very high pLDDT."""
        model = AlphaFoldModel(
            uniprot_id="P12345",
            model_version="v4",
            plddt_score=95.0
        )
        assert model.confidence_category == "very_high"
    
    def test_confidence_category_high(self):
        """Test confidence category for high pLDDT."""
        model = AlphaFoldModel(
            uniprot_id="P12345",
            model_version="v4",
            plddt_score=75.0
        )
        assert model.confidence_category == "high"
    
    def test_confidence_category_low(self):
        """Test confidence category for low pLDDT."""
        model = AlphaFoldModel(
            uniprot_id="P12345",
            model_version="v4",
            plddt_score=60.0
        )
        assert model.confidence_category == "low"
    
    def test_confidence_category_very_low(self):
        """Test confidence category for very low pLDDT."""
        model = AlphaFoldModel(
            uniprot_id="P12345",
            model_version="v4",
            plddt_score=40.0
        )
        assert model.confidence_category == "very_low"
    
    def test_confidence_category_none(self):
        """Test confidence category when pLDDT is None."""
        model = AlphaFoldModel(
            uniprot_id="P12345",
            model_version="v4",
            plddt_score=None
        )
        assert model.confidence_category is None


class TestAlphaFoldAPIClient:
    """Tests for AlphaFoldAPIClient."""
    
    def test_client_init(self):
        """Test client initialization."""
        client = AlphaFoldAPIClient()
        assert client.cache_dir is None
        assert client.session is not None
    
    def test_client_init_with_cache(self):
        """Test client initialization with cache directory."""
        client = AlphaFoldAPIClient(cache_dir="/tmp/cache")
        assert client.cache_dir == "/tmp/cache"
    
    @patch('src.alphafold_client.safe_api_call')
    @patch('src.alphafold_client.handle_api_response')
    def test_get_prediction_success(self, mock_handle, mock_safe_call):
        """Test successful prediction retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_safe_call.return_value = mock_response
        
        mock_data = [{
            "uniprotAccession": "P12345",
            "entryId": "AF-P12345-F1-model_v4",
            "ptmScore": 85.5,
            "sequenceLength": 300,
            "releaseDate": "2024-01-15"
        }]
        mock_handle.return_value = mock_data
        
        client = AlphaFoldAPIClient()
        model = client.get_prediction("P12345")
        
        assert model is not None
        assert model.uniprot_id == "P12345"
        assert model.model_version == "v4"
        assert model.plddt_score == 85.5
        assert model.sequence_length == 300
    
    @patch('src.alphafold_client.safe_api_call')
    def test_get_prediction_not_found(self, mock_safe_call):
        """Test prediction not found (404)."""
        from utils.exceptions import AlphaFoldAPIError
        mock_safe_call.side_effect = AlphaFoldAPIError("404: Not found", status_code=404)
        
        client = AlphaFoldAPIClient()
        model = client.get_prediction("INVALID")
        
        assert model is None
    
    @patch('src.alphafold_client.safe_api_call')
    def test_get_prediction_other_error(self, mock_safe_call):
        """Test other API errors."""
        mock_safe_call.side_effect = Exception("Network error")
        
        client = AlphaFoldAPIClient()
        model = client.get_prediction("P12345")
        
        assert model is None
    
    def test_extract_version_v4(self):
        """Test version extraction for v4."""
        client = AlphaFoldAPIClient()
        assert client._extract_version("AF-P12345-F1-model_v4") == "v4"
    
    def test_extract_version_v3(self):
        """Test version extraction for v3."""
        client = AlphaFoldAPIClient()
        assert client._extract_version("AF-P12345-F1-model_v3") == "v3"
    
    def test_extract_version_v2(self):
        """Test version extraction for v2."""
        client = AlphaFoldAPIClient()
        assert client._extract_version("AF-P12345-F1-model_v2") == "v2"
    
    def test_extract_version_default(self):
        """Test version extraction with no version info."""
        client = AlphaFoldAPIClient()
        assert client._extract_version("") == "v4"
        assert client._extract_version("AF-P12345-F1") == "v4"
    
    def test_construct_model_urls(self):
        """Test URL construction."""
        client = AlphaFoldAPIClient()
        pdb_url, cif_url = client._construct_model_urls("P12345", "v4")
        
        assert "AF-P12345-F1-model_v4.pdb" in pdb_url
        assert "AF-P12345-F1-model_v4.cif" in cif_url
        assert pdb_url.startswith("https://alphafold.ebi.ac.uk/files")
    
    @patch('src.alphafold_client.safe_api_call')
    def test_download_model_success(self, mock_safe_call):
        """Test successful model download."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"MODEL DATA"
        mock_safe_call.return_value = mock_response
        
        client = AlphaFoldAPIClient()
        content = client.download_model("P12345", format="pdb")
        
        assert content == b"MODEL DATA"
    
    @patch('src.alphafold_client.safe_api_call')
    def test_download_model_not_found(self, mock_safe_call):
        """Test model download when file not found."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_safe_call.return_value = mock_response
        
        client = AlphaFoldAPIClient()
        content = client.download_model("P12345", format="pdb")
        
        assert content is None
    
    def test_download_model_invalid_format(self):
        """Test download with invalid format."""
        client = AlphaFoldAPIClient()
        content = client.download_model("P12345", format="xyz")
        
        assert content is None
    
    @patch('src.alphafold_client.AlphaFoldAPIClient.get_prediction')
    def test_get_model_quality_info_exists(self, mock_get):
        """Test quality info when prediction exists."""
        mock_model = AlphaFoldModel(
            uniprot_id="P12345",
            model_version="v4",
            plddt_score=85.5,
            sequence_length=300,
            model_url="https://example.com/model.pdb"
        )
        mock_get.return_value = mock_model
        
        client = AlphaFoldAPIClient()
        info = client.get_model_quality_info("P12345")
        
        assert info["has_prediction"] is True
        assert info["plddt_score"] == 85.5
        assert info["confidence"] == "high"
        assert info["uniprot_id"] == "P12345"
    
    @patch('src.alphafold_client.AlphaFoldAPIClient.get_prediction')
    def test_get_model_quality_info_not_exists(self, mock_get):
        """Test quality info when prediction doesn't exist."""
        mock_get.return_value = None
        
        client = AlphaFoldAPIClient()
        info = client.get_model_quality_info("INVALID")
        
        assert info["has_prediction"] is False
        assert info["plddt_score"] is None
        assert "No AlphaFold prediction" in info["recommendation"]
    
    def test_generate_recommendation_very_high(self):
        """Test recommendation for very high confidence."""
        client = AlphaFoldAPIClient()
        rec = client._generate_recommendation(95.0)
        assert "Excellent quality" in rec
    
    def test_generate_recommendation_high(self):
        """Test recommendation for high confidence."""
        client = AlphaFoldAPIClient()
        rec = client._generate_recommendation(75.0)
        assert "Good quality" in rec
    
    def test_generate_recommendation_low(self):
        """Test recommendation for low confidence."""
        client = AlphaFoldAPIClient()
        rec = client._generate_recommendation(60.0)
        assert "Low confidence" in rec
    
    def test_generate_recommendation_very_low(self):
        """Test recommendation for very low confidence."""
        client = AlphaFoldAPIClient()
        rec = client._generate_recommendation(40.0)
        assert "Very low confidence" in rec
    
    def test_generate_recommendation_none(self):
        """Test recommendation when score is None."""
        client = AlphaFoldAPIClient()
        rec = client._generate_recommendation(None)
        assert "unavailable" in rec
    
    @patch('src.alphafold_client.AlphaFoldAPIClient.get_prediction')
    def test_check_availability_true(self, mock_get):
        """Test availability check when prediction exists."""
        mock_get.return_value = AlphaFoldModel("P12345", "v4")
        
        client = AlphaFoldAPIClient()
        assert client.check_availability("P12345") is True
    
    @patch('src.alphafold_client.AlphaFoldAPIClient.get_prediction')
    def test_check_availability_false(self, mock_get):
        """Test availability check when prediction doesn't exist."""
        mock_get.return_value = None
        
        client = AlphaFoldAPIClient()
        assert client.check_availability("INVALID") is False


class TestConvenienceFunction:
    """Tests for convenience function."""
    
    @patch('src.alphafold_client.AlphaFoldAPIClient.get_prediction')
    def test_get_alphafold_model(self, mock_get):
        """Test convenience function."""
        mock_model = AlphaFoldModel("P12345", "v4", plddt_score=85.0)
        mock_get.return_value = mock_model
        
        model = get_alphafold_model("P12345")
        
        assert model is not None
        assert model.uniprot_id == "P12345"
        mock_get.assert_called_once_with("P12345")


class TestParsePredictionData:
    """Tests for prediction data parsing."""
    
    def test_parse_list_response(self):
        """Test parsing list format response."""
        client = AlphaFoldAPIClient()
        data = [{
            "uniprotAccession": "P12345",
            "entryId": "AF-P12345-F1-model_v4",
            "ptmScore": 85.5
        }]
        
        model = client._parse_prediction_data(data)
        
        assert model is not None
        assert model.uniprot_id == "P12345"
    
    def test_parse_dict_response(self):
        """Test parsing dict format response."""
        client = AlphaFoldAPIClient()
        data = {
            "uniprotAccession": "P12345",
            "entryId": "AF-P12345-F1-model_v4",
            "confidenceScore": 90.0
        }
        
        model = client._parse_prediction_data(data)
        
        assert model is not None
        assert model.plddt_score == 90.0
    
    def test_parse_empty_response(self):
        """Test parsing empty response."""
        client = AlphaFoldAPIClient()
        model = client._parse_prediction_data([])
        
        assert model is None
    
    def test_parse_invalid_response(self):
        """Test parsing invalid response."""
        client = AlphaFoldAPIClient()
        model = client._parse_prediction_data("invalid")
        
        assert model is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
