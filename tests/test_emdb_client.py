"""
Unit tests for EMDB API client.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, '/Users/lijing/literature_agent-V2-claude/protein_evaluator')

from src.emdb_client import (
    EMDBAPIClient,
    EMDBEntry,
    get_emdb_entry,
    get_emdb_resolution
)


class TestEMDBEntry:
    """Tests for EMDBEntry dataclass."""
    
    def test_entry_creation(self):
        """Test creating EMDBEntry instance."""
        entry = EMDBEntry(
            emdb_id="EMD-1234",
            title="Test Structure",
            resolution=3.5,
            sample_name="Test Protein"
        )
        
        assert entry.emdb_id == "EMD-1234"
        assert entry.title == "Test Structure"
        assert entry.resolution == 3.5
        assert entry.sample_name == "Test Protein"
        assert entry.authors == []
        assert entry.related_pdb_ids == []
    
    def test_entry_with_defaults(self):
        """Test EMDBEntry default values."""
        entry = EMDBEntry(emdb_id="EMD-5678")
        
        assert entry.emdb_id == "EMD-5678"
        assert entry.title is None
        assert entry.authors == []
        assert entry.related_pdb_ids == []


class TestEMDBAPIClient:
    """Tests for EMDBAPIClient."""
    
    def test_client_init(self):
        """Test client initialization."""
        client = EMDBAPIClient()
        assert client.session is not None
    
    def test_normalize_emdb_id_standard(self):
        """Test normalizing standard EMDB ID."""
        client = EMDBAPIClient()
        assert client._normalize_emdb_id("EMD-1234") == "EMD-1234"
        assert client._normalize_emdb_id("emd-1234") == "EMD-1234"
    
    def test_normalize_emdb_id_numeric(self):
        """Test normalizing numeric ID."""
        client = EMDBAPIClient()
        assert client._normalize_emdb_id("1234") == "EMD-1234"
    
    def test_normalize_emdb_id_with_prefix_variations(self):
        """Test normalizing various prefix formats."""
        client = EMDBAPIClient()
        assert client._normalize_emdb_id("EMD_1234") == "EMD-1234"
        assert client._normalize_emdb_id("emd_5678") == "EMD-5678"
    
    def test_extract_numeric_id(self):
        """Test extracting numeric ID."""
        client = EMDBAPIClient()
        assert client._extract_numeric_id("EMD-1234") == "1234"
        assert client._extract_numeric_id("1234") == "1234"
    
    @patch('src.emdb_client.EMDBAPIClient._fetch_from_pdbe')
    @patch('src.emdb_client.EMDBAPIClient._fetch_from_emdb_api')
    def test_get_entry_from_pdbe(self, mock_emdb, mock_pdbe):
        """Test getting entry from PDBe API."""
        mock_entry = EMDBEntry(emdb_id="EMD-1234", title="Test")
        mock_pdbe.return_value = mock_entry
        mock_emdb.return_value = None
        
        client = EMDBAPIClient()
        entry = client.get_entry("1234")
        
        assert entry == mock_entry
        mock_pdbe.assert_called_once()
    
    @patch('src.emdb_client.EMDBAPIClient._fetch_from_pdbe')
    @patch('src.emdb_client.EMDBAPIClient._fetch_from_emdb_api')
    def test_get_entry_fallback_to_emdb(self, mock_emdb, mock_pdbe):
        """Test fallback to EMDB API."""
        mock_entry = EMDBEntry(emdb_id="EMD-1234", title="Test")
        mock_pdbe.return_value = None
        mock_emdb.return_value = mock_entry
        
        client = EMDBAPIClient()
        entry = client.get_entry("1234")
        
        assert entry == mock_entry
        mock_emdb.assert_called_once()
    
    @patch('src.emdb_client.EMDBAPIClient._fetch_from_pdbe')
    @patch('src.emdb_client.EMDBAPIClient._fetch_from_emdb_api')
    def test_get_entry_not_found(self, mock_emdb, mock_pdbe):
        """Test when entry not found."""
        mock_pdbe.return_value = None
        mock_emdb.return_value = None
        
        client = EMDBAPIClient()
        entry = client.get_entry("99999")
        
        assert entry is None
    
    def test_parse_pdbe_data_full(self):
        """Test parsing complete PDBe data."""
        client = EMDBAPIClient()
        
        mock_data = {
            "title": "Test Structure",
            "resolution": [{"value": 3.5, "method": "FSC 0.143"}],
            "emMethod": ["single particle"],
            "sample": {"name": "Test Protein", "organism": "Homo sapiens", "molecularWeight": 100.5},
            "pdbeId": ["1ABC", "1DEF"],
            "depositionDate": "2024-01-15",
            "releaseDate": "2024-03-01",
            "authors": ["Author A", "Author B"]
        }
        
        entry = client._parse_pdbe_data("EMD-1234", mock_data)
        
        assert entry.emdb_id == "EMD-1234"
        assert entry.title == "Test Structure"
        assert entry.resolution == 3.5
        assert entry.resolution_method == "FSC 0.143"
        assert entry.em_method == "single particle"
        assert entry.sample_name == "Test Protein"
        assert entry.sample_organism == "Homo sapiens"
        assert entry.molecular_weight == 100.5
        assert entry.related_pdb_ids == ["1ABC", "1DEF"]
        assert entry.deposition_date == "2024-01-15"
        assert entry.release_date == "2024-03-01"
        assert entry.authors == ["Author A", "Author B"]
    
    def test_parse_pdbe_data_minimal(self):
        """Test parsing minimal PDBe data."""
        client = EMDBAPIClient()
        
        mock_data = {"title": "Minimal Entry"}
        
        entry = client._parse_pdbe_data("EMD-5678", mock_data)
        
        assert entry.emdb_id == "EMD-5678"
        assert entry.title == "Minimal Entry"
        assert entry.resolution is None
    
    def test_parse_pdbe_data_resolution_dict(self):
        """Test parsing resolution as dict."""
        client = EMDBAPIClient()
        
        mock_data = {
            "resolution": {"value": 4.2, "method": "FSC 0.5"}
        }
        
        entry = client._parse_pdbe_data("EMD-9999", mock_data)
        
        assert entry.resolution == 4.2
        assert entry.resolution_method == "FSC 0.5"
    
    def test_parse_pdbe_data_empty_resolution(self):
        """Test parsing with zero resolution."""
        client = EMDBAPIClient()
        
        mock_data = {"resolution": {"value": 0}}
        
        entry = client._parse_pdbe_data("EMD-1111", mock_data)
        
        assert entry.resolution is None  # Should be None for 0
    
    def test_parse_emdb_data_basic(self):
        """Test parsing EMDB API data."""
        client = EMDBAPIClient()
        
        mock_data = {
            "deposition": {"title": "EMDB Test"},
            "map": {"resolution": {"value": 5.0, "method": "FSC"}},
            "structure_determination": {"method": "cryo-EM"}
        }
        
        entry = client._parse_emdb_data("EMD-2222", mock_data)
        
        assert entry.emdb_id == "EMD-2222"
        assert entry.title == "EMDB Test"
        assert entry.resolution == 5.0
        assert entry.em_method == "cryo-EM"
    
    def test_parse_emdb_data_list_response(self):
        """Test parsing EMDB data as list."""
        client = EMDBAPIClient()
        
        mock_data = [{
            "title": "List Entry",
            "map": {"resolution": {"value": 3.0}}
        }]
        
        entry = client._parse_emdb_data("EMD-3333", mock_data)
        
        assert entry.emdb_id == "EMD-3333"
        assert entry.resolution == 3.0
    
    def test_parse_emdb_data_invalid(self):
        """Test parsing invalid data."""
        client = EMDBAPIClient()
        
        entry = client._parse_emdb_data("EMD-4444", "invalid")
        
        assert entry.emdb_id == "EMD-4444"
        assert entry.title is None
    
    def test_get_related_pdb_entries_found(self):
        """Test getting related PDB entries."""
        client = EMDBAPIClient()
        mock_entry = EMDBEntry(
            emdb_id="EMD-1234",
            related_pdb_ids=["1ABC", "1DEF"]
        )
        
        with patch.object(client, 'get_entry', return_value=mock_entry):
            pdbs = client.get_related_pdb_entries("1234")
            assert pdbs == ["1ABC", "1DEF"]
    
    def test_get_related_pdb_entries_not_found(self):
        """Test when entry not found."""
        client = EMDBAPIClient()
        
        with patch.object(client, 'get_entry', return_value=None):
            pdbs = client.get_related_pdb_entries("99999")
            assert pdbs == []
    
    def test_get_resolution_info_found_high(self):
        """Test resolution info for high-res entry."""
        client = EMDBAPIClient()
        mock_entry = EMDBEntry(
            emdb_id="EMD-1234",
            resolution=2.5,
            resolution_method="FSC 0.143",
            em_method="single particle",
            title="High Res Structure"
        )
        
        with patch.object(client, 'get_entry', return_value=mock_entry):
            info = client.get_resolution_info("1234")
            
            assert info["found"] is True
            assert info["resolution"] == 2.5
            assert info["method"] == "FSC 0.143"
            assert info["em_method"] == "single particle"
            assert info["quality"] == "high"
            assert info["title"] == "High Res Structure"
    
    def test_get_resolution_info_found_medium(self):
        """Test resolution info for medium-res entry."""
        client = EMDBAPIClient()
        mock_entry = EMDBEntry(emdb_id="EMD-1234", resolution=4.0)
        
        with patch.object(client, 'get_entry', return_value=mock_entry):
            info = client.get_resolution_info("1234")
            assert info["quality"] == "medium"
    
    def test_get_resolution_info_found_low(self):
        """Test resolution info for low-res entry."""
        client = EMDBAPIClient()
        mock_entry = EMDBEntry(emdb_id="EMD-1234", resolution=8.0)
        
        with patch.object(client, 'get_entry', return_value=mock_entry):
            info = client.get_resolution_info("1234")
            assert info["quality"] == "low"
    
    def test_get_resolution_info_found_very_low(self):
        """Test resolution info for very low-res entry."""
        client = EMDBAPIClient()
        mock_entry = EMDBEntry(emdb_id="EMD-1234", resolution=15.0)
        
        with patch.object(client, 'get_entry', return_value=mock_entry):
            info = client.get_resolution_info("1234")
            assert info["quality"] == "very_low"
    
    def test_get_resolution_info_not_found(self):
        """Test resolution info when not found."""
        client = EMDBAPIClient()
        
        with patch.object(client, 'get_entry', return_value=None):
            info = client.get_resolution_info("99999")
            
            assert info["found"] is False
            assert info["resolution"] is None
            assert "not found" in info["message"]
    
    def test_check_exists_true(self):
        """Test exists check when found."""
        client = EMDBAPIClient()
        mock_entry = EMDBEntry(emdb_id="EMD-1234")
        
        with patch.object(client, 'get_entry', return_value=mock_entry):
            assert client.check_exists("1234") is True
    
    def test_check_exists_false(self):
        """Test exists check when not found."""
        client = EMDBAPIClient()
        
        with patch.object(client, 'get_entry', return_value=None):
            assert client.check_exists("99999") is False
    
    def test_search_by_resolution_placeholder(self):
        """Test resolution search placeholder."""
        client = EMDBAPIClient()
        results = client.search_by_resolution(min_res=3.0, max_res=5.0)
        assert results == []
    
    def test_get_entry_summary_found(self):
        """Test entry summary when found."""
        client = EMDBAPIClient()
        mock_entry = EMDBEntry(
            emdb_id="EMD-1234",
            title="Test Structure",
            sample_name="Protein X",
            resolution=3.5,
            em_method="cryo-EM",
            sample_organism="Human",
            related_pdb_ids=["1ABC"]
        )
        
        with patch.object(client, 'get_entry', return_value=mock_entry):
            summary = client.get_entry_summary("1234")
            
            assert summary["status"] == "found"
            assert summary["title"] == "Test Structure"
            assert summary["sample"] == "Protein X"
            assert summary["resolution"] == "3.50 Å"
            assert summary["method"] == "cryo-EM"
            assert summary["organism"] == "Human"
            assert summary["related_pdb"] == ["1ABC"]
    
    def test_get_entry_summary_not_found(self):
        """Test entry summary when not found."""
        client = EMDBAPIClient()
        
        with patch.object(client, 'get_entry', return_value=None):
            summary = client.get_entry_summary("99999")
            
            assert summary["status"] == "not_found"
            assert "Entry not found" in summary["message"]
    
    def test_get_entry_summary_no_resolution(self):
        """Test entry summary without resolution."""
        client = EMDBAPIClient()
        mock_entry = EMDBEntry(emdb_id="EMD-1234", title="No Res")
        
        with patch.object(client, 'get_entry', return_value=mock_entry):
            summary = client.get_entry_summary("1234")
            assert summary["resolution"] == "N/A"


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    @patch('src.emdb_client.EMDBAPIClient.get_entry')
    def test_get_emdb_entry(self, mock_get):
        """Test get_emdb_entry convenience function."""
        mock_entry = EMDBEntry(emdb_id="EMD-1234", title="Test")
        mock_get.return_value = mock_entry
        
        entry = get_emdb_entry("1234")
        
        assert entry == mock_entry
        mock_get.assert_called_once_with("1234")
    
    @patch('src.emdb_client.EMDBAPIClient.get_resolution_info')
    def test_get_emdb_resolution(self, mock_get):
        """Test get_emdb_resolution convenience function."""
        mock_data = {"emdb_id": "EMD-1234", "resolution": 3.5}
        mock_get.return_value = mock_data
        
        info = get_emdb_resolution("1234")
        
        assert info == mock_data
        mock_get.assert_called_once_with("1234")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
