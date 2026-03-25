"""
EMDB (Electron Microscopy Data Bank) API client.
Provides interface for querying EMDB entry metadata and associated information.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

import requests

from utils.api_utils import http_session, retry_with_backoff, safe_api_call, handle_api_response
from utils.exceptions import APIError

logger = logging.getLogger(__name__)


@dataclass
class EMDBEntry:
    """Represents an EMDB entry with metadata."""
    
    emdb_id: str  # Format: EMD-XXXX
    title: Optional[str] = None
    sample_name: Optional[str] = None
    resolution: Optional[float] = None  # In Angstroms
    resolution_method: Optional[str] = None  # e.g., "FSC 0.143"
    em_method: Optional[str] = None  # Electron microscopy method
    deposition_date: Optional[str] = None
    release_date: Optional[str] = None
    authors: List[str] = None
    citation: Optional[str] = None
    doi: Optional[str] = None
    related_pdb_ids: List[str] = None
    sample_organism: Optional[str] = None
    sample_cellular_component: Optional[str] = None
    molecular_weight: Optional[float] = None  # In kDa
    details_url: Optional[str] = None
    image_url: Optional[str] = None
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []
        if self.related_pdb_ids is None:
            self.related_pdb_ids = []


class EMDBAPIClient:
    """Client for EMDB API operations."""
    
    BASE_URL = "https://www.ebi.ac.uk/emdb/api"
    PDBe_URL = "https://www.ebi.ac.uk/pdbe/api"
    FTP_BASE = "ftp://ftp.ebi.ac.uk/pub/databases/emdb"
    
    def __init__(self):
        """Initialize EMDB API client."""
        self.session = http_session
        logger.info("EMDBAPIClient initialized")
    
    def _normalize_emdb_id(self, emdb_id: str) -> str:
        """
        Normalize EMDB ID to standard format (EMD-XXXX).
        
        Args:
            emdb_id: Raw EMDB ID (e.g., "emd-1234", "1234", "EMD-1234")
            
        Returns:
            Normalized EMDB ID
        """
        emdb_clean = emdb_id.upper().strip()
        # Remove 'EMD-' prefix if present
        emdb_clean = emdb_clean.replace("EMD-", "").replace("EMD_", "")
        # Remove any non-numeric characters
        emdb_clean = ''.join(c for c in emdb_clean if c.isdigit())
        return f"EMD-{emdb_clean}"
    
    def _extract_numeric_id(self, emdb_id: str) -> str:
        """Extract numeric part from EMDB ID."""
        normalized = self._normalize_emdb_id(emdb_id)
        return normalized.replace("EMD-", "")
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_entry(self, emdb_id: str) -> Optional[EMDBEntry]:
        """
        Get EMDB entry metadata.
        
        Args:
            emdb_id: EMDB ID (e.g., "EMD-1234" or "1234")
            
        Returns:
            EMDBEntry with metadata or None if not found
        """
        normalized_id = self._normalize_emdb_id(emdb_id)
        numeric_id = self._extract_numeric_id(emdb_id)
        
        # Try PDBe API first (more reliable)
        entry = self._fetch_from_pdbe(normalized_id, numeric_id)
        if entry:
            return entry
        
        # Fallback to EMDB API
        entry = self._fetch_from_emdb_api(normalized_id, numeric_id)
        if entry:
            return entry
        
        logger.info(f"No EMDB entry found for {normalized_id}")
        return None
    
    def _fetch_from_pdbe(self, emdb_id: str, numeric_id: str) -> Optional[EMDBEntry]:
        """Fetch EMDB data from PDBe API."""
        try:
            # Use PDBe API to get EMDB summary
            url = f"{self.PDBe_URL}/emdb/entry/summary/{emdb_id}"
            response = safe_api_call(
                url, session=self.session, timeout=30, error_class=APIError
            )
            data = handle_api_response(response, error_class=APIError)
            
            if emdb_id in data:
                return self._parse_pdbe_data(emdb_id, data[emdb_id])
            return None
            
        except Exception as e:
            logger.debug(f"PDBe API fetch failed for {emdb_id}: {e}")
            return None
    
    def _fetch_from_emdb_api(self, emdb_id: str, numeric_id: str) -> Optional[EMDBEntry]:
        """Fetch EMDB data from EMDB API."""
        try:
            # EMDB API endpoint
            url = f"{self.BASE_URL}/entry/{emdb_id}"
            response = safe_api_call(
                url, session=self.session, timeout=30, error_class=APIError
            )
            data = handle_api_response(response, error_class=APIError)
            
            return self._parse_emdb_data(emdb_id, data)
            
        except Exception as e:
            logger.debug(f"EMDB API fetch failed for {emdb_id}: {e}")
            return None
    
    def _parse_pdbe_data(self, emdb_id: str, data: Dict) -> EMDBEntry:
        """Parse PDBe API response into EMDBEntry."""
        try:
            # Extract resolution
            resolution = None
            resolution_method = None
            if "resolution" in data:
                res_data = data["resolution"]
                if isinstance(res_data, list) and len(res_data) > 0:
                    resolution = float(res_data[0].get("value", 0))
                    resolution_method = res_data[0].get("method")
                elif isinstance(res_data, dict):
                    resolution = float(res_data.get("value", 0))
                    resolution_method = res_data.get("method")
            
            # Extract EM method
            em_method = data.get("emMethod", [None])[0] if isinstance(data.get("emMethod"), list) else data.get("emMethod")
            
            # Extract sample info
            sample_name = None
            sample_organism = None
            molecular_weight = None
            if "sample" in data:
                sample = data["sample"]
                if isinstance(sample, list) and len(sample) > 0:
                    sample = sample[0]
                if isinstance(sample, dict):
                    sample_name = sample.get("name")
                    sample_organism = sample.get("organism")
                    mol_wt = sample.get("molecularWeight")
                    if mol_wt:
                        molecular_weight = float(mol_wt) if isinstance(mol_wt, (int, float, str)) else None
            
            # Extract related PDB IDs
            related_pdb_ids = []
            if "pdbeId" in data:
                pdb_ids = data["pdbeId"]
                if isinstance(pdb_ids, list):
                    related_pdb_ids = [pdb.upper() for pdb in pdb_ids]
                elif isinstance(pdb_ids, str):
                    related_pdb_ids = [pdb_ids.upper()]
            
            # Extract dates
            deposition_date = data.get("depositionDate")
            release_date = data.get("releaseDate")
            
            # Extract authors
            authors = []
            if "authors" in data:
                auth_data = data["authors"]
                if isinstance(auth_data, list):
                    authors = auth_data
                elif isinstance(auth_data, str):
                    authors = [auth_data]
            
            # Extract title
            title = data.get("title")
            
            return EMDBEntry(
                emdb_id=emdb_id,
                title=title,
                sample_name=sample_name,
                resolution=resolution if resolution and resolution > 0 else None,
                resolution_method=resolution_method,
                em_method=em_method,
                deposition_date=deposition_date,
                release_date=release_date,
                authors=authors,
                related_pdb_ids=related_pdb_ids,
                sample_organism=sample_organism,
                molecular_weight=molecular_weight,
                details_url=f"https://www.ebi.ac.uk/emdb/entry/{emdb_id}",
                image_url=f"https://www.ebi.ac.uk/emdb/entry/{emdb_id}/images"
            )
            
        except Exception as e:
            logger.error(f"Error parsing PDBe data for {emdb_id}: {e}")
            return EMDBEntry(emdb_id=emdb_id)
    
    def _parse_emdb_data(self, emdb_id: str, data: Dict) -> EMDBEntry:
        """Parse EMDB API response into EMDBEntry."""
        try:
            # Handle different response structures
            if isinstance(data, list) and len(data) > 0:
                entry_data = data[0]
            elif isinstance(data, dict):
                entry_data = data
            else:
                return EMDBEntry(emdb_id=emdb_id)
            
            # Extract basic info
            title = entry_data.get("deposition", {}).get("title") or entry_data.get("title")
            
            # Extract resolution from various possible paths
            resolution = None
            res_method = None
            if "map" in entry_data:
                map_data = entry_data["map"]
                if "resolution" in map_data:
                    res = map_data["resolution"]
                    if isinstance(res, dict):
                        resolution = float(res.get("value", 0)) if res.get("value") else None
                        res_method = res.get("method")
                    elif isinstance(res, (int, float)):
                        resolution = float(res)
            
            # Extract EM method
            em_method = None
            if "structure_determination" in entry_data:
                struct_det = entry_data["structure_determination"]
                if isinstance(struct_det, list) and len(struct_det) > 0:
                    struct_det = struct_det[0]
                if isinstance(struct_det, dict):
                    em_method = struct_det.get("method")
            
            return EMDBEntry(
                emdb_id=emdb_id,
                title=title,
                resolution=resolution if resolution and resolution > 0 else None,
                resolution_method=res_method,
                em_method=em_method,
                details_url=f"https://www.ebi.ac.uk/emdb/entry/{emdb_id}",
                image_url=f"https://www.ebi.ac.uk/emdb/entry/{emdb_id}/images"
            )
            
        except Exception as e:
            logger.error(f"Error parsing EMDB data for {emdb_id}: {e}")
            return EMDBEntry(emdb_id=emdb_id)
    
    def get_related_pdb_entries(self, emdb_id: str) -> List[str]:
        """
        Get PDB entries associated with an EMDB entry.
        
        Args:
            emdb_id: EMDB ID
            
        Returns:
            List of PDB IDs
        """
        entry = self.get_entry(emdb_id)
        if entry and entry.related_pdb_ids:
            return entry.related_pdb_ids
        return []
    
    def get_resolution_info(self, emdb_id: str) -> Dict[str, Any]:
        """
        Get resolution information for an EMDB entry.
        
        Args:
            emdb_id: EMDB ID
            
        Returns:
            Dictionary with resolution data
        """
        entry = self.get_entry(emdb_id)
        
        if not entry:
            return {
                "emdb_id": self._normalize_emdb_id(emdb_id),
                "found": False,
                "resolution": None,
                "method": None,
                "quality": "unknown",
                "message": "Entry not found in EMDB"
            }
        
        # Determine quality based on resolution
        quality = "unknown"
        if entry.resolution:
            if entry.resolution <= 3.0:
                quality = "high"
            elif entry.resolution <= 5.0:
                quality = "medium"
            elif entry.resolution <= 10.0:
                quality = "low"
            else:
                quality = "very_low"
        
        return {
            "emdb_id": entry.emdb_id,
            "found": True,
            "resolution": entry.resolution,
            "method": entry.resolution_method,
            "em_method": entry.em_method,
            "quality": quality,
            "title": entry.title
        }
    
    def check_exists(self, emdb_id: str) -> bool:
        """
        Check if EMDB entry exists.
        
        Args:
            emdb_id: EMDB ID
            
        Returns:
            True if entry exists
        """
        entry = self.get_entry(emdb_id)
        return entry is not None
    
    def search_by_resolution(self, min_res: Optional[float] = None, 
                             max_res: Optional[float] = None,
                             limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search EMDB entries by resolution range.
        
        Note: This is a placeholder. EMDB API doesn't support direct resolution search.
        Would need to use PDBe search or download full index.
        
        Args:
            min_res: Minimum resolution (Angstroms)
            max_res: Maximum resolution (Angstroms)
            limit: Maximum results to return
            
        Returns:
            List of matching entries
        """
        logger.warning("EMDB resolution search not implemented - requires indexed data")
        return []
    
    def get_entry_summary(self, emdb_id: str) -> Dict[str, Any]:
        """
        Get a concise summary of an EMDB entry.
        
        Args:
            emdb_id: EMDB ID
            
        Returns:
            Summary dictionary
        """
        entry = self.get_entry(emdb_id)
        
        if not entry:
            return {
                "emdb_id": self._normalize_emdb_id(emdb_id),
                "status": "not_found",
                "message": "Entry not found in EMDB"
            }
        
        return {
            "emdb_id": entry.emdb_id,
            "status": "found",
            "title": entry.title,
            "sample": entry.sample_name,
            "resolution": f"{entry.resolution:.2f} Å" if entry.resolution else "N/A",
            "method": entry.em_method,
            "organism": entry.sample_organism,
            "related_pdb": entry.related_pdb_ids,
            "url": entry.details_url
        }


# Convenience function
def get_emdb_entry(emdb_id: str) -> Optional[EMDBEntry]:
    """
    Get EMDB entry (convenience function).
    
    Args:
        emdb_id: EMDB ID
        
    Returns:
        EMDBEntry or None
    """
    client = EMDBAPIClient()
    return client.get_entry(emdb_id)


def get_emdb_resolution(emdb_id: str) -> Dict[str, Any]:
    """
    Get EMDB resolution info (convenience function).
    
    Args:
        emdb_id: EMDB ID
        
    Returns:
        Resolution information dictionary
    """
    client = EMDBAPIClient()
    return client.get_resolution_info(emdb_id)
