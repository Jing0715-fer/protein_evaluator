"""
API clients for external services.
Provides unified interfaces for UniProt, PDB, BLAST, and PubMed APIs.
"""

import logging
import time
import subprocess
import re
import urllib.parse
from typing import Dict, List, Optional, Any
from datetime import datetime

import requests
import xml.etree.ElementTree as ET

from utils.api_utils import (
    http_session,
    retry_with_backoff,
    retry_on_api_error,
    handle_api_response,
    safe_api_call
)
from utils.exceptions import (
    UniProtAPIError,
    PDBAPIError,
    BLASTSearchError,
    PubMedAPIError
)

logger = logging.getLogger(__name__)


class UniProtClient:
    """Client for UniProt API operations."""

    BASE_URL = "http://rest.uniprot.org/uniprotkb"
    SEARCH_URL = "http://rest.uniprot.org/uniprotkb/search"

    def __init__(self):
        self.session = http_session

    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_protein(self, uniprot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get protein data from UniProt.

        Args:
            uniprot_id: UniProt ID

        Returns:
            Parsed protein data or None on failure
        """
        url = f"{self.BASE_URL}/{uniprot_id}?format=json"

        try:
            response = safe_api_call(
                url, session=self.session, timeout=30, error_class=UniProtAPIError
            )
            data = handle_api_response(response, error_class=UniProtAPIError)
            return self._parse_protein_data(data)
        except Exception as e:
            logger.error(f"Failed to get UniProt data for {uniprot_id}: {e}")
            return None

    def _parse_protein_data(self, data: Dict) -> Dict[str, Any]:
        """Parse UniProt API response into structured data."""
        uniprot_id = data.get('primaryAccession', '')
        entry_name = data.get('uniProtkbId', '')

        # Protein name
        protein_name = ''
        protein_desc = data.get('proteinDescription', {})
        if protein_desc.get('recommendedName'):
            protein_name = protein_desc['recommendedName'].get('fullName', {}).get('value', '')

        # Gene names
        gene_names = []
        genes = data.get('genes', [])
        for gene in genes:
            if gene.get('geneName'):
                gene_names.append(gene['geneName'].get('value', ''))
            for syn in gene.get('synonyms', []):
                gene_names.append(syn.get('value', ''))

        # Organism
        organism = ''
        org_data = data.get('organism', {})
        if org_data:
            organism = org_data.get('scientificName', '')

        # Function
        function = self._extract_function(data)

        # Sequence
        sequence_length = 0
        protein_sequence = ''
        sequence_info = data.get('sequence', {})
        if sequence_info:
            sequence_length = sequence_info.get('length', 0)
            protein_sequence = sequence_info.get('value', '')

        # Molecular weight
        mass = sequence_info.get('molWeight', 0)

        # PDB IDs
        pdb_ids = []
        for ref in data.get('uniProtKBCrossReferences', []):
            if ref.get('database') == 'PDB':
                pdb_ids.append(ref.get('id', ''))

        # Keywords
        keywords = self._extract_keywords(data)

        return {
            'uniprot_id': uniprot_id,
            'entry_name': entry_name,
            'protein_name': protein_name,
            'gene_names': gene_names,
            'organism': organism,
            'function': function,
            'sequence': protein_sequence,
            'sequence_length': sequence_length,
            'mass': mass,
            'pdb_ids': list(set(pdb_ids)),
            'keywords': keywords,
            'raw_data': data
        }

    def _extract_function(self, data: Dict) -> str:
        """Extract function description from UniProt data."""
        function = ''
        try:
            comments = data.get('comments', [])
            if isinstance(comments, list):
                for comment in comments:
                    if comment.get('commentType') == 'FUNCTION' or comment.get('type') == 'function':
                        texts = comment.get('texts', [])
                        if isinstance(texts, list) and len(texts) > 0:
                            first_text = texts[0]
                            if isinstance(first_text, dict):
                                function = first_text.get('value', '')
                        if function:
                            break

            # Fallback: try proteinDescription
            if not function:
                protein_desc = data.get('proteinDescription', {})
                for name_type in ['recommendedName', 'alternativeNames', 'subunitName']:
                    name_data = protein_desc.get(name_type, {})
                    if isinstance(name_data, dict):
                        full_name = name_data.get('fullName', {})
                        if isinstance(full_name, dict):
                            fn = full_name.get('value', '')
                            if fn and len(fn) > 50:
                                function = fn
                                break
        except Exception as e:
            logger.warning(f"Failed to extract function: {e}")

        return function

    def _extract_keywords(self, data: Dict) -> List[str]:
        """Extract keywords from UniProt data."""
        keywords = []
        try:
            kw_list = data.get('keywords', [])
            if isinstance(kw_list, list):
                for kw in kw_list:
                    if isinstance(kw, dict):
                        kw_obj = kw.get('keyword')
                        if isinstance(kw_obj, dict):
                            val = kw_obj.get('value')
                            if val:
                                keywords.append(val)
        except Exception as e:
            logger.warning(f"Failed to extract keywords: {e}")
        return keywords

    @retry_with_backoff(max_retries=2, initial_delay=1.0)
    def get_sequence(self, uniprot_id: str) -> Optional[str]:
        """Get protein sequence for a UniProt ID."""
        url = f"{self.BASE_URL}/{uniprot_id}?format=json"
        try:
            response = safe_api_call(url, session=self.session, timeout=30)
            data = handle_api_response(response)
            seq_info = data.get('sequence', {})
            if isinstance(seq_info, dict):
                return seq_info.get('value', '')
            elif isinstance(seq_info, str):
                return seq_info
            return None
        except Exception as e:
            logger.error(f"Failed to get sequence for {uniprot_id}: {e}")
            return None

    def search_by_organism(self, taxonomy_id: int, limit: int = 20) -> List[Dict]:
        """Search proteins by organism taxonomy ID."""
        params = {
            'query': f'organism_id:{taxonomy_id}',
            'format': 'json',
            'size': limit,
            'fields': 'accession,gene_names,protein_name,organism_name'
        }

        try:
            response = self.session.get(self.SEARCH_URL, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                results = []
                for entry in data.get('results', []):
                    results.append({
                        'uniprot_id': entry.get('primaryAccession', ''),
                        'entry_name': '',
                        'protein_name': self._extract_protein_name(entry),
                        'organism': entry.get('organism', {}).get('scientificName', ''),
                        'identity': None,
                        'score': None
                    })
                return results
        except Exception as e:
            logger.error(f"Search by organism failed: {e}")
        return []

    def search_with_pdb(self, taxonomy_id: Optional[int] = None, limit: int = 20) -> List[Dict]:
        """Search proteins with PDB structures."""
        query = 'database:pdb'
        if taxonomy_id:
            query = f'database:pdb AND organism_id:{taxonomy_id}'

        params = {
            'query': query,
            'format': 'json',
            'size': limit,
            'fields': 'accession,gene_names,protein_name,organism_name',
            'sort': 'score desc'
        }

        try:
            response = self.session.get(self.SEARCH_URL, params=params, timeout=60)
            if response.status_code == 200:
                data = response.json()
                return self._parse_search_results(data)
        except Exception as e:
            logger.error(f"Search with PDB failed: {e}")
        return []

    def _parse_search_results(self, data: Dict) -> List[Dict]:
        """Parse search results."""
        results = []
        for entry in data.get('results', []):
            accession = entry.get('primaryAccession', '')
            gene_names = entry.get('genes', [])
            gene_name = gene_names[0].get('geneName', {}).get('value', '') if gene_names else ''

            results.append({
                'uniprot_id': accession,
                'entry_name': gene_name,
                'protein_name': self._extract_protein_name(entry),
                'organism': entry.get('organism', {}).get('scientificName', ''),
                'identity': None,
                'score': None
            })
        return results

    def _extract_protein_name(self, entry: Dict) -> str:
        """Extract protein name from entry."""
        protein_rec = entry.get('proteinDescription', {})
        if isinstance(protein_rec, dict):
            rec_name = protein_rec.get('recommendedName', {})
            if isinstance(rec_name, dict):
                full_name = rec_name.get('fullName', {})
                if isinstance(full_name, dict):
                    return full_name.get('value', '')[:100]
        return ''


class PDBClient:
    """Client for PDB/RCSB API operations."""

    RCSB_URL = "https://data.rcsb.org/rest/v1/core/entry"
    PDBe_URL = "https://www.ebi.ac.uk/pdbe/api/pdb/entry"

    def __init__(self):
        self.session = http_session

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    def get_structure(self, pdb_id: str) -> Optional[Dict]:
        """
        Get PDB structure metadata.

        Args:
            pdb_id: PDB ID

        Returns:
            Structure data or None on failure
        """
        url = f"{self.RCSB_URL}/{pdb_id}"

        try:
            response = safe_api_call(
                url, session=self.session, timeout=30, error_class=PDBAPIError
            )
            data = handle_api_response(response, error_class=PDBAPIError)
            result = self._parse_structure_data(pdb_id, data)
            
            # Fetch entity list
            try:
                entity_list = self._get_entity_list(pdb_id)
                if entity_list:
                    result['entity_list'] = entity_list
            except Exception as e:
                logger.warning(f"Failed to get entity list for {pdb_id}: {e}")
            
            return result
        except Exception as e:
            logger.error(f"Failed to get PDB data for {pdb_id}: {e}")
            return None

    def _get_entity_list(self, pdb_id: str) -> List[Dict]:
        """Get entity list from PDBe API."""
        url = f"{self.PDBe_URL}/molecules/{pdb_id}"
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                # API returns {"9dom": [...]} - use lowercase
                pdb_key = pdb_id.lower()
                entities_data = data.get(pdb_key) or data.get(pdb_id.upper()) or []
                
                result = []
                for ent in entities_data:
                    # Get chain info - prefer 'in_chains' or build from chains info
                    chains = ent.get('in_chains', [])
                    chain_str = chains[0] if chains else ''
                    
                    # Get sequence for this entity
                    sequence = ent.get('sequence', {}).get('seq_one_letter_code', '') if isinstance(ent.get('sequence'), dict) else ''
                    
                    # Get molecule type - map to simpler format
                    mol_type = ent.get('molecule_type', '')
                    if 'polypeptide' in str(mol_type).lower():
                        polymer_type = 'Polypeptide'
                    elif 'nucleotide' in str(mol_type).lower() or ' nucleic ' in str(mol_type).lower():
                        polymer_type = 'Nucleic Acid'
                    else:
                        polymer_type = str(mol_type) if mol_type else 'Unknown'
                    
                    result.append({
                        'entity_id': ent.get('entity_id'),
                        'chain': chain_str,
                        'polymer_type': polymer_type,
                        'sequence': sequence,
                        'molecule_name': ent.get('molecule_name', [''])[0] if ent.get('molecule_name') else '',
                        'gene_name': ent.get('gene_name', [''])[0] if ent.get('gene_name') else '',
                        'length': ent.get('length'),
                        'organism': ent.get('source', [{}])[0].get('organism_scientific_name', '') if ent.get('source') else '',
                    })
                return result
        except Exception as e:
            logger.warning(f"Failed to fetch entity list for {pdb_id}: {e}")
        return []

    def _parse_structure_data(self, pdb_id: str, data: Dict) -> Dict:
        """Parse RCSB API response."""
        # Initialize top-level fields
        title = ''
        experimental_method = ''
        resolution = None
        deposition_date = ''
        authors = []

        # Title
        try:
            struct_data = data.get('struct', {})
            if isinstance(struct_data, dict):
                title_val = struct_data.get('title')
                title = title_val if isinstance(title_val, str) else ''
        except Exception as e:
            logger.warning(f"Failed to parse title for {pdb_id}: {e}")

        # Method
        try:
            exptl = data.get('exptl', [])
            if isinstance(exptl, list) and len(exptl) > 0:
                experimental_method = exptl[0].get('method', '')
        except Exception as e:
            logger.warning(f"Failed to parse method for {pdb_id}: {e}")

        # Resolution
        try:
            if 'rcsb_entry_info' in data:
                info = data['rcsb_entry_info']
                if isinstance(info, dict):
                    res = info.get('resolution_combined', [])
                    if isinstance(res, list) and len(res) > 0:
                        resolution = res[0]
        except Exception as e:
            logger.warning(f"Failed to parse resolution for {pdb_id}: {e}")

        # Date
        try:
            audit = data.get('audit', {})
            if isinstance(audit, dict):
                deposition_date = audit.get('creation_date', '')
        except Exception as e:
            logger.warning(f"Failed to parse date for {pdb_id}: {e}")

        # Authors
        try:
            audit_author = data.get('audit_author', [])
            if isinstance(audit_author, list):
                authors = [a.get('name', '') for a in audit_author if isinstance(a, dict)]
        except Exception as e:
            logger.warning(f"Failed to parse authors for {pdb_id}: {e}")

        # Citations
        citations = self._extract_citations(data)

        # Entity info
        entity_info = {}
        try:
            if 'rcsb_entry_info' in data:
                info = data['rcsb_entry_info']
                if isinstance(info, dict):
                    entity_info = {
                        'polypeptide': info.get('polymer_entity_count', 0),
                        'ligand': info.get('ligand_entity_count', 0),
                        'water': info.get('water_entity_count', 0),
                        'nucleic_acid': info.get('nonpolymer_entity_count', 0),
                    }
        except Exception as e:
            logger.warning(f"Failed to parse entity info for {pdb_id}: {e}")

        return {
            'pdb_id': pdb_id,
            'title': title,
            'experimental_method': experimental_method,
            'resolution': resolution,
            'deposition_date': deposition_date,
            'authors': authors,
            'citations': citations,
            'entity_info': entity_info
        }

    def _extract_citations(self, data: Dict) -> List[Dict]:
        """Extract citations from PDB data."""
        citations = []
        try:
            citation_list = data.get('citation', [])
            if not isinstance(citation_list, list):
                return citations

            for cit in citation_list:
                if not isinstance(cit, dict):
                    continue

                citation = {
                    'id': cit.get('id', ''),
                    'title': cit.get('title', ''),
                    'journal': cit.get('journal_abbrev', ''),
                    'year': cit.get('year', ''),
                    'pubmed_id': None,
                    'doi': None,
                    'abstract': ''
                }

                # PubMed ID
                for ref in cit.get('db_reference', []):
                    if isinstance(ref, dict) and ref.get('db_name') == 'PubMed':
                        citation['pubmed_id'] = ref.get('db_code')
                        break

                # DOI
                for ref in cit.get('db_reference', []):
                    if isinstance(ref, dict) and ref.get('db_name') == 'DOI':
                        citation['doi'] = ref.get('db_code')
                        break

                citations.append(citation)
        except Exception as e:
            logger.warning(f"Failed to extract citations: {e}")

        return citations

    def get_structures_batch(self, pdb_ids: List[str], max_structures: int = None) -> Dict[str, Any]:
        """
        Get multiple PDB structures.

        Args:
            pdb_ids: List of PDB IDs
            max_structures: Maximum number of structures to fetch (None means no limit)

        Returns:
            Dictionary with structures list
        """
        structures = []
        # Use provided max_structures, None means no limit
        if max_structures is not None:
            pdb_ids_to_fetch = pdb_ids[:max_structures]
            logger.info(f"Fetching {len(pdb_ids_to_fetch)} PDB structures (limit: {max_structures})")
        else:
            pdb_ids_to_fetch = pdb_ids
            logger.info(f"Fetching all {len(pdb_ids_to_fetch)} PDB structures (no limit)")

        for idx, pdb_id in enumerate(pdb_ids_to_fetch):
            try:
                structure = self.get_structure(pdb_id)
                if structure:
                    structures.append(structure)
            except Exception as e:
                logger.warning(f"Failed to fetch PDB {pdb_id}: {e}")

        return {
            'pdb_ids': pdb_ids_to_fetch,
            'structures': structures
        }

    @retry_with_backoff(max_retries=2, initial_delay=1.0)
    def search_by_sequence(self, sequence: str, evaluation_id: int = None) -> Dict[str, Any]:
        """
        Search PDB by sequence similarity using PDBe API.

        Args:
            sequence: Protein sequence
            evaluation_id: Evaluation ID for logging

        Returns:
            Search results with PDB data
        """
        if not sequence:
            return {'query_id': None, 'results': [], 'method': 'pdbe_search', 'pdb_data': None}

        search_url = "https://www.ebi.ac.uk/pdbe/api/pdb/sequence/similar"

        session = requests.Session()
        session.headers.update({'Content-Type': 'application/json', 'Accept': 'application/json'})

        search_data = {
            "sequence": sequence[:10000],
            "Evalue": 10,
            "sequenceId": "query"
        }

        try:
            search_resp = session.post(search_url, json=search_data, timeout=120)

            if search_resp.status_code != 200:
                raise PDBAPIError(f"PDBe search failed: {search_resp.status_code}")

            search_json = search_resp.json()
            pdb_ids = []
            results = []

            for entry in search_json:
                pdb_id = entry.get('alignment', [{}])[0].get('pdb_id', '')
                if pdb_id and len(pdb_id) == 4 and pdb_id not in pdb_ids:
                    pdb_ids.append(pdb_id)
                    identity = entry.get('alignment', [{}])[0].get('identity', 0)
                    results.append({
                        'pdb_id': pdb_id,
                        'title': f"PDB {pdb_id}",
                        'identity': int(identity * 100) if identity else None,
                        'score': entry.get('score', 0)
                    })

            # Get metadata for found PDBs
            pdb_data = None
            if pdb_ids:
                pdb_data = self.get_structures_batch(pdb_ids)

            return {
                'query_id': None,
                'results': results[:20],
                'method': 'pdbe_search',
                'pdb_data': pdb_data
            }

        except Exception as e:
            logger.error(f"PDBe sequence search failed: {e}")
            raise PDBAPIError(f"Sequence search failed: {e}")


class BLASTClient:
    """Client for BLAST search operations."""

    def __init__(self):
        self.session = http_session
        self.uniprot_client = UniProtClient()

    def search(
        self,
        uniprot_id: str,
        protein_sequence: str = None,
        evaluation_id: int = None
    ) -> Dict[str, Any]:
        """Run BLAST search for similar proteins."""
        # Try NCBI qBLAST first
        try:
            return self._run_ncbi_qblast(uniprot_id, protein_sequence, evaluation_id)
        except Exception as e:
            logger.warning(f"NCBI qBLAST failed: {e}, trying fallback search...")

        # Fallback to UniProt-based search
        return self._fallback_search(uniprot_id, protein_sequence, evaluation_id)

    def _run_ncbi_qblast(
        self,
        uniprot_id: str,
        protein_sequence: str = None,
        evaluation_id: int = None
    ) -> Dict[str, Any]:
        """Run NCBI qBLAST search."""
        # Get sequence if not provided
        if not protein_sequence and uniprot_id:
            protein_sequence = self.uniprot_client.get_sequence(uniprot_id)

        if not protein_sequence:
            raise BLASTSearchError("No protein sequence available")

        logger.info(f"Starting NCBI qBLAST search for sequence of length {len(protein_sequence)}")

        # Submit BLAST job
        job_id = self._submit_blast_job(protein_sequence)
        if not job_id:
            raise BLASTSearchError("Failed to submit BLAST job")

        logger.info(f"BLAST job submitted: {job_id}")

        # Wait for results
        results = self._wait_for_blast_results(job_id)

        # Parse results
        parsed_results = self._parse_blast_results(results, uniprot_id)

        # Get PDB metadata if found
        pdb_data = None
        if parsed_results.get('pdb_ids'):
            pdb_client = PDBClient()
            pdb_data = pdb_client.get_structures_batch(parsed_results['pdb_ids'])

        return {
            'query_id': uniprot_id,
            'results': parsed_results['results'][:20],
            'method': 'ncbi_qblast',
            'pdb_data': pdb_data
        }

    def _submit_blast_job(self, protein_sequence: str) -> Optional[str]:
        """Submit BLAST job to NCBI."""
        try:
            query_params = urllib.parse.urlencode({
                'CMD': 'Put',
                'QUERY': protein_sequence[:10000],
                'DATABASE': 'pdb',
                'PROGRAM': 'blastp',
                'EXPECT': 0.01,
                'HITLIST_SIZE': 50,
                'FILTER': 'L',
                'FORMAT_TYPE': 'XML'
            })

            cmd = [
                'curl', '-s', '-X', 'POST',
                '-d', query_params,
                'https://blast.ncbi.nlm.nih.gov/Blast.cgi'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                logger.error(f"curl BLAST submission failed: {result.stderr}")
                return None

            # Parse RID from response
            match = re.search(r'RID = (\w+)', result.stdout)
            if match:
                return match.group(1)

            return None
        except Exception as e:
            logger.error(f"Failed to submit BLAST job: {e}")
            return None

    def _wait_for_blast_results(self, job_id: str, max_wait: int = 300) -> str:
        """Wait for and retrieve BLAST results."""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                # Check status
                status_cmd = [
                    'curl', '-s',
                    f'https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=Get&FORMAT_OBJECT=Status&RID={job_id}'
                ]

                status_result = subprocess.run(status_cmd, capture_output=True, text=True, timeout=30)

                if 'Status=READY' in status_result.stdout:
                    # Get results
                    results_cmd = [
                        'curl', '-s',
                        f'https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=Get&FORMAT_TYPE=XML&RID={job_id}'
                    ]

                    results = subprocess.run(results_cmd, capture_output=True, text=True, timeout=60)

                    if results.returncode == 0:
                        return results.stdout

                elif 'Status=WAITING' in status_result.stdout:
                    time.sleep(10)
                    continue
                else:
                    raise BLASTSearchError(f"BLAST job failed or unknown status")

            except Exception as e:
                logger.warning(f"BLAST polling error: {e}")
                time.sleep(10)

        raise BLASTSearchError(f"BLAST search timeout after {max_wait}s")

    def _parse_blast_results(self, xml_results: str, query_id: str) -> Dict[str, Any]:
        """Parse BLAST XML results."""
        results = []
        pdb_ids = []

        try:
            root = ET.fromstring(xml_results)

            # Find all hits
            for hit in root.findall('.//Hit'):
                hit_id = hit.findtext('Hit_id', '')
                hit_def = hit.findtext('Hit_def', '')
                hit_accession = hit.findtext('Hit_accession', '')

                # Extract PDB ID
                pdb_id = None
                if hit_accession and len(hit_accession) >= 4:
                    pdb_id = hit_accession[:4].upper()

                # Get HSP info
                hsp = hit.find('.//Hsp')
                if hsp is not None:
                    identity = hsp.findtext('Hsp_identity', '0')
                    align_len = hsp.findtext('Hsp_align-len', '1')
                    identity_pct = (int(identity) / int(align_len) * 100) if align_len != '0' else 0

                    score = hsp.findtext('Hsp_score', '0')
                    # Get E-value with fallback
                    evalue_elem = hsp.find('Hsp_evalue')
                    if evalue_elem is not None and evalue_elem.text:
                        evalue_str = evalue_elem.text.strip()
                    else:
                        # Try attribute or other variations
                        evalue_str = hsp.get('expect', '0')
                    # Try parsing as float (handles scientific notation)
                    try:
                        evalue_float = float(evalue_str) if evalue_str else 0.0
                    except (ValueError, TypeError):
                        evalue_float = 0.0
                        logger.warning(f"Could not parse evalue '{evalue_str}' for {pdb_id}")

                    if pdb_id and pdb_id not in pdb_ids:
                        pdb_ids.append(pdb_id)
                        results.append({
                            'pdb_id': pdb_id,
                            'title': hit_def[:200] if hit_def else f"PDB {pdb_id}",
                            'identity': round(identity_pct, 1),
                            'score': float(score) if score else 0,
                            'evalue': evalue_float
                        })
        except Exception as e:
            logger.error(f"Failed to parse BLAST results: {e}")

        return {'results': results, 'pdb_ids': pdb_ids}

    def _fallback_search(
        self,
        uniprot_id: str,
        protein_sequence: str = None,
        evaluation_id: int = None
    ) -> Dict[str, Any]:
        """Fallback search using UniProt PDB search."""
        results = []
        taxonomy_id = None

        try:
            # Get taxonomy ID
            if uniprot_id:
                protein_data = self.uniprot_client.get_protein(uniprot_id)
                if protein_data:
                    raw_data = protein_data.get('raw_data', {})
                    organism = raw_data.get('organism', {})
                    taxonomy_id = organism.get('taxonId')

            # Search with taxonomy filter
            pdb_results = self.uniprot_client.search_with_pdb(taxonomy_id, limit=20)

            # Filter out query protein
            for r in pdb_results:
                if r['uniprot_id'] != uniprot_id:
                    results.append(r)

        except Exception as e:
            logger.error(f"Fallback search failed: {e}")

        return {
            'query_id': uniprot_id,
            'results': results[:20],
            'method': 'uniprot_fallback',
            'pdb_data': None
        }


class PubMedClient:
    """Client for PubMed/Entrez API operations."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self):
        self.session = http_session

    @retry_with_backoff(max_retries=2, initial_delay=1.0)
    def get_article(self, pubmed_id: str) -> Optional[Dict[str, Any]]:
        """Get PubMed article information."""
        url = f"{self.BASE_URL}/efetch.fcgi"
        params = {
            'db': 'pubmed',
            'id': pubmed_id,
            'rettype': 'abstract',
            'retmode': 'xml'
        }

        try:
            response = safe_api_call(
                url, method="GET", session=self.session, params=params,
                timeout=30, error_class=PubMedAPIError
            )

            xml_content = response.text
            return self._parse_pubmed_xml(xml_content, pubmed_id)

        except Exception as e:
            logger.error(f"Failed to get PubMed article {pubmed_id}: {e}")
            return None

    def _parse_pubmed_xml(self, xml_content: str, pubmed_id: str) -> Optional[Dict]:
        """Parse PubMed XML response."""
        try:
            root = ET.fromstring(xml_content)

            article = root.find('.//PubmedArticle')
            if article is None:
                return None

            # Title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else ''

            # Abstract - can have multiple sections, so concatenate all
            abstract_parts = []
            for abstract_elem in article.findall('.//AbstractText'):
                if abstract_elem.text:
                    abstract_parts.append(abstract_elem.text)
            abstract = ' '.join(abstract_parts)

            # Journal
            journal_elem = article.find('.//Title')
            journal = journal_elem.text if journal_elem is not None else ''

            # Year
            year_elem = article.find('.//PubDate/Year')
            year = year_elem.text if year_elem is not None else ''

            # Authors
            authors = []
            for author in article.findall('.//Author'):
                last_name = author.findtext('LastName', '')
                fore_name = author.findtext('ForeName', '')
                if last_name:
                    authors.append(f"{fore_name} {last_name}".strip())

            return {
                'pubmed_id': pubmed_id,
                'title': title,
                'abstract': abstract,
                'journal': journal,
                'year': year,
                'authors': authors
            }

        except Exception as e:
            logger.error(f"Failed to parse PubMed XML for {pubmed_id}: {e}")
            return None

    def get_abstract_simple(self, pubmed_id: str) -> Optional[str]:
        """Get just the abstract text for a PubMed ID."""
        article = self.get_article(pubmed_id)
        if article:
            return article.get('abstract', '')
        return None

    def search_by_title(self, title: str) -> Optional[str]:
        """Search PubMed by article title and return PMID.

        Uses three strategies:
        1. Exact title match with quotes
        2. Flexible search with key terms
        3. Try search without special characters
        """
        if not title or len(title) < 10:
            return None

        import re
        url = f"{self.BASE_URL}/esearch.fcgi"

        # Clean title for search - remove special characters but keep letters/numbers/spaces
        def clean_title_for_search(t):
            # Remove special characters but keep basic alphanumeric and spaces
            cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', t)
            # Collapse multiple spaces
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            return cleaned

        cleaned_title = clean_title_for_search(title)

        # Strategy 1: Try exact title match with cleaned title
        params = {
            'db': 'pubmed',
            'term': f'"{cleaned_title}"[Title]',
            'retmax': 1,
            'retmode': 'json'
        }

        try:
            response = safe_api_call(
                url, method="GET", session=self.session, params=params,
                timeout=15, error_class=PubMedAPIError
            )
            result = response.json()
            id_list = result.get('esearchresult', {}).get('idlist', [])
            if id_list:
                logger.info(f"Found PMID {id_list[0]} via exact title match")
                return id_list[0]
        except Exception as e:
            logger.warning(f"Failed exact title search: {e}")

        # Strategy 2: Extract key terms from cleaned title and search flexibly
        # Use cleaned title for better matching
        words = cleaned_title.split()
        stop_words = {'from', 'with', 'that', 'this', 'have', 'were', 'been',
                      'also', 'they', 'their', 'these', 'which', 'will', 'would',
                      'structural', 'basis', 'human', 'protein', 'channel', 'molecular'}
        key_terms = [w for w in words if len(w) > 4 and w.lower() not in stop_words]
        if len(key_terms) < 3:
            key_terms = [w for w in words if len(w) > 3]

        if key_terms:
            search_term = ' '.join(key_terms[:8])  # Use up to 8 key terms
            params = {
                'db': 'pubmed',
                'term': search_term,
                'retmax': 5,
                'retmode': 'json'
            }

            try:
                response = safe_api_call(
                    url, method="GET", session=self.session, params=params,
                    timeout=15, error_class=PubMedAPIError
                )
                result = response.json()
                id_list = result.get('esearchresult', {}).get('idlist', [])
                # Verify by fetching and checking title similarity
                for pmid in id_list:
                    article = self.get_article(pmid)
                    if article:
                        article_title = article.get('title', '').lower()
                        # Check if there's significant word overlap
                        title_words = set(w.lower() for w in cleaned_title.split() if len(w) > 3)
                        article_words = set(w.lower() for w in article_title.split() if len(w) > 3)
                        overlap = title_words & article_words
                        if len(overlap) >= min(5, len(title_words) * 0.4):
                            logger.info(f"Found PMID {pmid} via flexible search, overlap: {overlap}")
                            return pmid
            except Exception as e:
                logger.warning(f"Failed flexible title search: {e}")

        # Strategy 3: Try searching with just the first few significant words
        significant_words = [w for w in cleaned_title.split() if len(w) > 5][:5]
        if significant_words:
            search_term = ' '.join(significant_words) + '[Title/Abstract]'
            params = {
                'db': 'pubmed',
                'term': search_term,
                'retmax': 10,
                'retmode': 'json'
            }
            try:
                response = safe_api_call(
                    url, method="GET", session=self.session, params=params,
                    timeout=15, error_class=PubMedAPIError
                )
                result = response.json()
                id_list = result.get('esearchresult', {}).get('idlist', [])
                for pmid in id_list:
                    article = self.get_article(pmid)
                    if article:
                        article_title = article.get('title', '').lower()
                        title_words = set(w.lower() for w in cleaned_title.split() if len(w) > 3)
                        article_words = set(w.lower() for w in article_title.split() if len(w) > 3)
                        overlap = title_words & article_words
                        if len(overlap) >= min(4, len(title_words) * 0.35):
                            logger.info(f"Found PMID {pmid} via strategy 3, overlap: {overlap}")
                            return pmid
            except Exception as e:
                logger.warning(f"Failed strategy 3 title search: {e}")

        logger.warning(f"Could not find PMID for title: {title[:50]}...")
        return None

        return None

    def fetch_abstracts_for_structures(self, pdb_data: Dict) -> Dict:
        """Fetch PubMed abstracts for all citations in PDB structures."""
        for struct in pdb_data.get('structures', []):
            citations = struct.get('citations', [])
            for cit in citations:
                pubmed_id = cit.get('pubmed_id')
                title = cit.get('title', '')

                # If no PMID, try to find it by title search
                if not pubmed_id and title:
                    try:
                        pubmed_id = self.search_by_title(title)
                        if pubmed_id:
                            cit['pubmed_id'] = pubmed_id
                            logger.info(f"Found PMID {pubmed_id} via title search for: {title[:50]}...")
                    except Exception as e:
                        logger.warning(f"Failed to search PMID by title: {e}")

                # Fetch abstract if we have a PMID now
                if pubmed_id:
                    try:
                        abstract = self.get_abstract_simple(str(pubmed_id))
                        if abstract:
                            cit['abstract'] = abstract
                            logger.info(f"Retrieved abstract for PMID {pubmed_id}")
                    except Exception as e:
                        logger.warning(f"Failed to get abstract for PMID {pubmed_id}: {e}")

        return pdb_data
