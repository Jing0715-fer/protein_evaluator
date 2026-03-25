# pdb_fetcher.py
import requests
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class PDBFetcher:
    """PDB信息获取器 - 使用test.py的高效方法"""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.pdbe_base_url = "https://www.ebi.ac.uk/pdbe/api"    
    def fetch_pdb_complete_info(self, pdb_id: str) -> Dict[str, Any]:
        """
        获取PDB完整信息（基本信息+实体+UniProt映射+EMDB关联）
        """
        pdb_id = pdb_id.lower()
        result = {
            'basic_info': {},
            'entities': [],
            'uniprot_mappings': [],
            'uniprot_details': {},
            'related_emdb_ids': []  # 新增：存储关联的EMDB
        }
        
        try:
            # 1. 获取基本信息
            basic_info = self._fetch_basic_info(pdb_id)
            if basic_info:
                result['basic_info'] = basic_info
            
            # 2. 获取实体信息
            entities = self._fetch_entities(pdb_id)
            if entities:
                result['entities'] = entities
            
            # 3. 获取UniProt映射
            uniprot_data = self._fetch_uniprot_mappings(pdb_id)
            if uniprot_data:
                result['uniprot_mappings'] = uniprot_data['mappings']
                result['uniprot_details'] = uniprot_data['details']
            
            # 4. 【新增】获取关联的EMDB ID (使用PDBe API)
            emdb_ids = self._fetch_related_emdb_ids(pdb_id)
            result['related_emdb_ids'] = emdb_ids
            
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.error(f"获取PDB完整信息失败 {pdb_id}: {e}")
        
        return result

    def _fetch_related_emdb_ids(self, pdb_id: str) -> List[str]:
        """
        从PDBe API获取关联的EMDB ID
        """
        emdb_ids = []
        try:
            # 使用PDBe API获取关联实验数据
            url = f"{self.pdbe_base_url}/pdb/entry/related_experimental_data/{pdb_id}"
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if pdb_id in data:
                    for entry in data[pdb_id]:
                        if entry.get("database") == "EMDB":
                            emdb_id = entry.get("accession_code", "")
                            if emdb_id:
                                # 标准化格式
                                emdb_clean = emdb_id.upper()
                                if not emdb_clean.startswith("EMD-"):
                                    emdb_clean = f"EMD-{emdb_clean}"
                                emdb_ids.append(emdb_clean)
            
            return list(set(emdb_ids))
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"获取EMDB关联失败 {pdb_id}: {e}")
            return []
    
    def _fetch_basic_info(self, pdb_id: str) -> Optional[Dict]:
        """从RCSB获取基本信息"""
        try:
            url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                try:
                    return response.json()
                except (json.JSONDecodeError, ValueError) as json_error:
                    logger.warning(f"解析JSON失败 {pdb_id}: {json_error}")
                    return None
            else:
                logger.warning(f"获取基本信息失败 {pdb_id}: HTTP {response.status_code}")
                return None
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"获取基本信息失败 {pdb_id}: {e}")
        return None
    
    def _fetch_entities(self, pdb_id: str) -> List[Dict]:
        """从RCSB获取所有实体信息"""
        entities = []
        entity_id = 1
        
        while True:
            try:
                url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity_id}"
                response = requests.get(url, timeout=self.timeout)
                
                if response.status_code == 200:
                    entity_data = response.json()
                    entities.append(self._normalize_entity(entity_data, entity_id))
                    entity_id += 1
                else:
                    if entity_id > 1:
                        break
                    else:
                        logger.warning(f"未找到实体信息: {pdb_id}")
                        break
            except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
                logger.warning(f"获取实体失败 {pdb_id}/{entity_id}: {e}")
                break
        
        return entities
    
    def _fetch_uniprot_mappings(self, pdb_id: str) -> Dict[str, Any]:
        """
        从PDBe获取UniProt映射和详细信息
        
        返回:
            {
                'mappings': list,  # UniProt映射列表
                'details': dict    # uniprot_id -> 详细信息
            }
        """
        result = {'mappings': [], 'details': {}}
        
        try:
            # 获取映射关系
            pdbe_url = f"https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/{pdb_id}"
            response = requests.get(pdbe_url, timeout=self.timeout)
            
            if response.status_code == 200:
                pdbe_data = response.json()
                if pdb_id in pdbe_data:
                    uniprot_mappings = pdbe_data[pdb_id].get('UniProt', {})
                    
                    # 处理每个UniProt映射
                    for uniprot_id, chains_data in uniprot_mappings.items():
                        # 获取UniProt详细信息
                        uniprot_detail = self._fetch_uniprot_details(uniprot_id)
                        
                        mapping_info = {
                            'uniprot_id': uniprot_id,
                            'chains': self._normalize_chains_data(chains_data)
                        }
                        
                        result['mappings'].append(mapping_info)
                        if uniprot_detail:
                            result['details'][uniprot_id] = uniprot_detail
            
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.error(f"获取UniProt映射失败 {pdb_id}: {e}")
        
        return result
    
    def _fetch_uniprot_details(self, uniprot_id: str) -> Optional[Dict]:
        """获取UniProt详细信息"""
        try:
            url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}"
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                uniprot_data = response.json()
                return self._normalize_uniprot_data(uniprot_data)
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"获取UniProt详情失败 {uniprot_id}: {e}")
        return None
    
    def _normalize_entity(self, entity_data: Dict, entity_id: int) -> Dict:
        """标准化实体数据"""
        container_ids = entity_data.get('rcsb_polymer_entity_container_identifiers', {})
        entity_poly = entity_data.get('entity_poly', {})
        source_org = entity_data.get('rcsb_entity_source_organism', [{}])
        
        return {
            'entity_id': str(entity_id),
            'asym_ids': container_ids.get('asym_ids', []),
            'chain_ids': container_ids.get('auth_asym_ids', []),
            'sequence': entity_poly.get('pdbx_seq_one_letter_code_can', ''),
            'description': entity_poly.get('pdbx_description', ''),
            'length': len(entity_poly.get('pdbx_seq_one_letter_code_can', '')),
            'source_organism': source_org[0] if source_org else {},
            'entity_data': entity_data  # 保留原始数据
        }
    
    def _normalize_chains_data(self, chains_data: Any) -> List[Dict]:
        """标准化链数据"""
        chains = []
        
        if isinstance(chains_data, list):
            chains = chains_data
        elif isinstance(chains_data, dict):
            chains = [chains_data]
        
        return chains
    
    def _normalize_uniprot_data(self, uniprot_data: Dict) -> Dict:
        """标准化UniProt数据"""
        protein_desc = uniprot_data.get('proteinDescription', {})
        rec_name = protein_desc.get('recommendedName', {})
        
        genes = uniprot_data.get('genes', [])
        gene_name = genes[0].get('geneName', {}).get('value', '') if genes else ''
        
        organism = uniprot_data.get('organism', {})
        scientific_name = organism.get('scientificName', '')
        
        sequence = uniprot_data.get('sequence', {})
        
        # 提取功能注释
        function_text = ''
        comments = uniprot_data.get('comments', [])
        for comment in comments:
            if comment.get('commentType') == 'FUNCTION':
                texts = comment.get('texts', [])
                if texts:
                    function_text = texts[0].get('value', '')
                    break
        
        return {
            'uniprot_id': uniprot_data.get('accession', ''),
            'entry_name': uniprot_data.get('uniProtkbId', ''),
            'protein_name': rec_name.get('fullName', {}).get('value', ''),
            'gene_names': [gene_name] if gene_name else [],
            'organism': scientific_name,
            'organism_id': organism.get('taxonId', ''),
            'function': function_text,
            'sequence_length': sequence.get('length', 0),
            'mass': uniprot_data.get('sequence', {}).get('molWeight', 0),
            'keywords': [kw.get('name', '') for kw in uniprot_data.get('keywords', [])],
            'uniprot_data': uniprot_data  # 保留原始数据
        }