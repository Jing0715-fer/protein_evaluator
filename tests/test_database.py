"""
Tests for database module
"""
import os
import sys
import pytest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base


class TestDatabase:
    """Test cases for database functions"""

    @pytest.fixture
    def test_db(self):
        """Create a temporary test database"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        yield session, db_path

        session.close()
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_create_evaluation(self, test_db):
        """Test creating a new evaluation"""
        session, db_path = test_db
        from src.database import create_protein_evaluation
        from src.models import ProteinEvaluation

        eval_obj = create_protein_evaluation(
            uniprot_id="P12345",
            gene_name="TEST",
            protein_name="Test Protein"
        )
        assert eval_obj is not None
        assert eval_obj.id is not None
        assert eval_obj.uniprot_id == "P12345"

    def test_get_evaluation(self, test_db):
        """Test retrieving an evaluation"""
        session, db_path = test_db
        from src.database import create_protein_evaluation, get_protein_evaluation

        eval_obj = create_protein_evaluation(
            uniprot_id="P12345",
            protein_name="Test Protein"
        )
        evaluation = get_protein_evaluation(eval_obj.id)
        assert evaluation is not None
        assert evaluation.uniprot_id == "P12345"

    def test_update_evaluation(self, test_db):
        """Test updating an evaluation"""
        session, db_path = test_db
        from src.database import create_protein_evaluation, update_protein_evaluation, get_protein_evaluation

        eval_obj = create_protein_evaluation(uniprot_id="P12345", protein_name="Test Protein")
        update_protein_evaluation(eval_obj.id, {'evaluation_status': 'completed', 'progress': 100})
        evaluation = get_protein_evaluation(eval_obj.id)
        assert evaluation.evaluation_status == "completed"
        assert evaluation.progress == 100

    def test_delete_evaluation(self, test_db):
        """Test deleting an evaluation"""
        session, db_path = test_db
        from src.database import create_protein_evaluation, delete_protein_evaluation, get_protein_evaluation

        eval_obj = create_protein_evaluation(uniprot_id="P12345", protein_name="Test Protein")
        result = delete_protein_evaluation(eval_obj.id)
        assert result is True
        evaluation = get_protein_evaluation(eval_obj.id)
        assert evaluation is None

    def test_search_evaluations(self, test_db):
        """Test searching evaluations"""
        session, db_path = test_db
        from src.database import create_protein_evaluation, search_protein_evaluations

        create_protein_evaluation(uniprot_id="P11111", protein_name="Alpha Protein")
        create_protein_evaluation(uniprot_id="P22222", protein_name="Beta Protein")
        results = search_protein_evaluations("alpha")
        assert len(results) >= 1

    def test_get_all_evaluations(self, test_db):
        """Test listing all evaluations"""
        session, db_path = test_db
        from src.database import create_protein_evaluation, get_all_protein_evaluations

        create_protein_evaluation(uniprot_id="P11111", protein_name="Protein 1")
        create_protein_evaluation(uniprot_id="P22222", protein_name="Protein 2")
        evaluations = get_all_protein_evaluations()
        assert len(evaluations) >= 2
