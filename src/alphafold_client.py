"""
AlphaFold Database API client.
Provides interface for querying AlphaFold structure predictions from EBI AlphaFold DB.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

import requests

from utils.api_utils import http_session, retry_with_backoff, safe_api_call, handle_api_response
from utils.exceptions import AlphaFoldAPIError

logger = logging.getLogger(__name__)


@dataclass
class AlphaFoldModel:
    """Represents an AlphaFold structure prediction model."""
    
    uniprot_id: str
    model_version: str  # 'v2' or 'v3' or 'v4'
    plddt_score: Optional[float] = None
    model_url: Optional[str] = None
    cif_url: Optional[str] = None
    pdb_url: Optional[str] = None
    confidence_category: Optional[str] = None  # 'very_high', 'high', 'low', 'very_low'
    sequence_length: Optional[int] = None
    created_date: Optional[str] = None
    
    def __post_init__(self):
        """Set confidence category based on pLDDT score."""
        if self.plddt_score is not None:
            if self.plddt_score >= 90:
                self.confidence_category = "very_high"
            elif self.plddt_score >= 70:
                self.confidence_category = "high"
            elif self.plddt_score >= 50:
                self.confidence_category = "low"
            else:
                self.confidence_category = "very_low"


class AlphaFoldAPIClient:
    """Client for AlphaFold Structure Database API operations."""
    
    BASE_URL = "https://alphafold.ebi.ac.uk/api"
    FILES_URL = "https://alphafold.ebi.ac.uk/files"
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize AlphaFold API client.
        
        Args:
            cache_dir: Optional directory for caching model files
        """
        self.session = http_session
        self.cache_dir = cache_dir
        logger.info("AlphaFoldAPIClient initialized")
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_prediction(self, uniprot_id: str) -> Optional[AlphaFoldModel]:
        """
        Get AlphaFold prediction for a UniProt ID.
        
        Args:
            uniprot_id: UniProt accession ID
            
        Returns:
            AlphaFoldModel with prediction data or None if not found
        """
        url = f"{self.BASE_URL}/prediction/{uniprot_id}"
        
        try:
            response = safe_api_call(
                url, session=self.session, timeout=30, error_class=AlphaFoldAPIError
            )
            data = handle_api_response(response, error_class=AlphaFoldAPIError)
            return self._parse_prediction_data(data)
        except AlphaFoldAPIError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                logger.info(f"No AlphaFold prediction found for {uniprot_id}")
                return None
            logger.error(f"Failed to get AlphaFold prediction for {uniprot_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching AlphaFold data for {uniprot_id}: {e}")
            return None
    
    def _parse_prediction_data(self, data: Dict) -> Optional[AlphaFoldModel]:
        """Parse AlphaFold API response into AlphaFoldModel."""
        try:
            # Handle both single prediction and list responses
            if isinstance(data, list) and len(data) > 0:
                prediction = data[0]
            elif isinstance(data, dict):
                prediction = data
            else:
                logger.warning("Unexpected AlphaFold API response format")
                return None
            
            uniprot_id = prediction.get('uniprotAccession', '')
            if not uniprot_id:
                uniprot_id = prediction.get('uniprot_id', '')
            
            # Get model version from entryId or construct it
            entry_id = prediction.get('entryId', '')
            model_version = self._extract_version(entry_id)
            
            # Get pLDDT scores if available
            plddt_score = None
            if 'ptmScore' in prediction:
                plddt_score = float(prediction['ptmScore'])
            elif 'confidenceScore' in prediction:
                plddt_score = float(prediction['confidenceScore'])
            
            # Get sequence length
            sequence_length = prediction.get('sequenceLength') or prediction.get('sequence', {}).get('length')
            
            # Construct file URLs
            pdb_url, cif_url = self._construct_model_urls(uniprot_id, model_version)
            
            return AlphaFoldModel(
                uniprot_id=uniprot_id,
                model_version=model_version,
                plddt_score=plddt_score,
                model_url=pdb_url,  # Default to PDB
                cif_url=cif_url,
                pdb_url=pdb_url,
                sequence_length=sequence_length,
                created_date=prediction.get('releaseDate') or prediction.get('creation_date')
            )
            
        except Exception as e:
            logger.error(f"Error parsing AlphaFold prediction data: {e}")
            return None
    
    def _extract_version(self, entry_id: str) -> str:
        """Extract model version from entry ID."""
        if not entry_id:
            return "v4"  # Default to latest
        
        # Entry ID format: AF-{uniprot_id}-F1-model_v4
        if "_v4" in entry_id or "-v4" in entry_id:
            return "v4"
        elif "_v3" in entry_id or "-v3" in entry_id:
            return "v3"
        elif "_v2" in entry_id or "-v2" in entry_id:
            return "v2"
        
        return "v4"  # Default to v4 (AF3/AF2 latest)
    
    def _construct_model_urls(self, uniprot_id: str, version: str = "v4") -> Tuple[str, str]:
        """
        Construct PDB and CIF file URLs for a UniProt ID.
        
        Args:
            uniprot_id: UniProt accession
            version: Model version (v2, v3, v4)
            
        Returns:
            Tuple of (pdb_url, cif_url)
        """
        # AF3 uses v4 format, AF2 uses v3 or v2
        pdb_url = f"{self.FILES_URL}/AF-{uniprot_id}-F1-model_{version}.pdb"
        cif_url = f"{self.FILES_URL}/AF-{uniprot_id}-F1-model_{version}.cif"
        
        return pdb_url, cif_url
    
    def download_model(self, uniprot_id: str, format: str = "pdb", 
                       version: str = "v4") -> Optional[bytes]:
        """
        Download AlphaFold model file.
        
        Args:
            uniprot_id: UniProt accession
            format: File format ('pdb' or 'cif')
            version: Model version
            
        Returns:
            File content as bytes or None on failure
        """
        if format.lower() == "pdb":
            url = f"{self.FILES_URL}/AF-{uniprot_id}-F1-model_{version}.pdb"
        elif format.lower() == "cif":
            url = f"{self.FILES_URL}/AF-{uniprot_id}-F1-model_{version}.cif"
        else:
            logger.error(f"Unsupported format: {format}")
            return None
        
        try:
            logger.info(f"Downloading AlphaFold model from {url}")
            response = safe_api_call(
                url, session=self.session, timeout=60, error_class=AlphaFoldAPIError
            )
            
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(f"Model file not found at {url} (status: {response.status_code})")
                return None
                
        except Exception as e:
            logger.error(f"Failed to download AlphaFold model: {e}")
            return None
    
    def get_model_quality_info(self, uniprot_id: str) -> Dict[str, Any]:
        """
        Get comprehensive model quality information.
        
        Args:
            uniprot_id: UniProt accession
            
        Returns:
            Dictionary with quality metrics
        """
        model = self.get_prediction(uniprot_id)
        
        if not model:
            return {
                "uniprot_id": uniprot_id,
                "has_prediction": False,
                "plddt_score": None,
                "confidence": None,
                "recommendation": "No AlphaFold prediction available for this protein"
            }
        
        recommendation = self._generate_recommendation(model.plddt_score)
        
        return {
            "uniprot_id": uniprot_id,
            "has_prediction": True,
            "plddt_score": model.plddt_score,
            "confidence": model.confidence_category,
            "model_version": model.model_version,
            "sequence_length": model.sequence_length,
            "model_url": model.model_url,
            "recommendation": recommendation
        }
    
    def _generate_recommendation(self, plddt_score: Optional[float]) -> str:
        """Generate usage recommendation based on pLDDT score."""
        if plddt_score is None:
            return "Quality information unavailable"
        
        if plddt_score >= 90:
            return "Excellent quality - suitable for all structural analyses including ligand docking and molecular dynamics"
        elif plddt_score >= 70:
            return "Good quality - reliable for overall fold and domain analysis"
        elif plddt_score >= 50:
            return "Low confidence - use with caution, may indicate disordered regions"
        else:
            return "Very low confidence - structure predictions may be unreliable"
    
    def check_availability(self, uniprot_id: str) -> bool:
        """
        Check if AlphaFold prediction exists for a UniProt ID.
        
        Args:
            uniprot_id: UniProt accession
            
        Returns:
            True if prediction exists
        """
        model = self.get_prediction(uniprot_id)
        return model is not None


# Convenience function for quick lookups
def get_alphafold_model(uniprot_id: str) -> Optional[AlphaFoldModel]:
    """
    Get AlphaFold model for a UniProt ID (convenience function).
    
    Args:
        uniprot_id: UniProt accession
        
    Returns:
        AlphaFoldModel or None
    """
    client = AlphaFoldAPIClient()
    return client.get_prediction(uniprot_id)
