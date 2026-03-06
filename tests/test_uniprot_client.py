"""
Tests for UniProt client module
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.uniprot_client import UniProtAPIClient, UniProtEntry, ProteinTarget


class TestUniProtAPIClient:
    """Test cases for UniProtAPIClient"""

    def test_client_init(self):
        """Test client initialization"""
        client = UniProtAPIClient(timeout=30)
        assert client.timeout == 30
        assert client.base_url == "http://rest.uniprot.org"

    def test_client_with_cache_dir(self):
        """Test client with custom cache directory"""
        client = UniProtAPIClient(cache_dir="test_cache")
        assert client.cache_dir.name == "test_cache"


class TestUniProtEntry:
    """Test cases for UniProtEntry dataclass"""

    def test_uniprot_entry_creation(self):
        """Test creating a UniProtEntry"""
        entry = UniProtEntry(
            uniprot_id="P12345",
            entry_name="TEST_HUMAN",
            protein_name="Test Protein",
            gene_names=["TEST"],
            organism="Homo sapiens",
            organism_id=9606,
            sequence_length=100,
            mass=11000,
            pdb_ids=["1ABC", "2DEF"],
            keywords=["Keyword1", "Keyword2"]
        )

        assert entry.uniprot_id == "P12345"
        assert entry.protein_name == "Test Protein"
        assert len(entry.pdb_ids) == 2
        assert entry.gene_names == ["TEST"]


class TestProteinTarget:
    """Test cases for ProteinTarget dataclass"""

    def test_protein_target_creation(self):
        """Test creating a ProteinTarget"""
        target = ProteinTarget(
            uniprot_id="P12345",
            protein_name="Test Protein",
            gene_names=["TEST"],
            organism="Homo sapiens",
            structure_ids=["1ABC"],
            preferred_structure_id="1ABC",
            confidence_score=0.95
        )

        assert target.uniprot_id == "P12345"
        assert target.confidence_score == 0.95
        assert len(target.structure_ids) == 1
        assert target.gene_names == ["TEST"]

    def test_protein_target_defaults(self):
        """Test ProteinTarget default values"""
        target = ProteinTarget(
            uniprot_id="P12345",
            protein_name="Test Protein",
            gene_names=["TEST"],
            organism="Homo sapiens",
            structure_ids=[]
        )

        assert target.confidence_score == 1.0
        assert target.preferred_structure_id is None
        assert target.evidence_sources == []
