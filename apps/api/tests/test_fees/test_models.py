from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy import inspect

from sqlalchemy import UniqueConstraint

from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.infrastructure.database import Base


def test_fee_type_model_registered():
    assert "fee_types" in Base.metadata.tables


def test_fee_structure_model_registered():
    assert "fee_structures" in Base.metadata.tables


def test_fee_due_model_registered():
    assert "fee_dues" in Base.metadata.tables


def test_payment_model_registered():
    assert "payments" in Base.metadata.tables


def test_fee_type_table_name():
    assert FeeType.__tablename__ == "fee_types"


def test_fee_structure_table_name():
    assert FeeStructure.__tablename__ == "fee_structures"


def test_fee_due_table_name():
    assert FeeDue.__tablename__ == "fee_dues"


def test_payment_table_name():
    assert Payment.__tablename__ == "payments"


def test_fee_type_columns():
    table = Base.metadata.tables["fee_types"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["name"].nullable is False
    assert cols["name"].type.length == 100
    assert cols["description"].nullable is True
    assert cols["status"].nullable is False
    assert cols["status"].type.length == 20
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_fee_structure_columns():
    table = Base.metadata.tables["fee_structures"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["academic_year_id"].nullable is False
    assert cols["class_id"].nullable is False
    assert cols["fee_type_id"].nullable is False
    assert cols["amount"].nullable is False
    assert cols["frequency"].nullable is False
    assert cols["status"].nullable is False
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_fee_due_columns():
    table = Base.metadata.tables["fee_dues"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["student_id"].nullable is False
    assert cols["academic_year_id"].nullable is False
    assert cols["fee_structure_id"].nullable is False
    assert cols["original_amount"].nullable is False
    assert cols["amount_paid"].nullable is False
    assert cols["due_date"].nullable is True
    assert cols["status"].nullable is False
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_payment_columns():
    table = Base.metadata.tables["payments"]
    cols = {c.name: c for c in table.columns}

    assert cols["id"].primary_key is True
    assert cols["student_id"].nullable is False
    assert cols["fee_due_id"].nullable is False
    assert cols["amount"].nullable is False
    assert cols["payment_date"].nullable is True
    assert cols["payment_method"].nullable is True
    assert cols["receipt_number"].nullable is True
    assert cols["created_at"].nullable is False


def test_fee_type_unique_constraint():
    table = Base.metadata.tables["fee_types"]
    uq = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    assert any("name" in [col.name for col in c.columns] for c in uq)


def test_fee_structure_unique_constraint():
    table = Base.metadata.tables["fee_structures"]
    uq = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    assert any("uq_fee_structure_per_year_class_type" == c.name for c in uq if c.name)


def test_fee_due_unique_constraint():
    table = Base.metadata.tables["fee_dues"]
    uq = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    assert any("uq_fee_due_per_student_structure" == c.name for c in uq if c.name)


def test_payment_receipt_unique():
    table = Base.metadata.tables["payments"]
    uq = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    assert len(uq) >= 1
    receipt_cols = [col for col in table.columns if col.name == "receipt_number"]
    assert receipt_cols[0].unique is True


def test_monetary_fields_are_integers():
    assert isinstance(FeeStructure.amount.type, type(Base.metadata.tables["fee_structures"].c.amount.type).__class__) or True
    assert FeeStructure.amount.type.python_type is int


def test_instance_creation_fee_type():
    ft = FeeType(name="Tuition", description="Tuition fee", status="active")
    assert ft.name == "Tuition"
    assert ft.description == "Tuition fee"
    assert ft.status == "active"


def test_instance_creation_fee_structure():
    fs = FeeStructure(
        academic_year_id=1, class_id=1, fee_type_id=1, amount=50000,
        frequency="annual", status="active",
    )
    assert fs.amount == 50000
    assert fs.frequency == "annual"
    assert fs.status == "active"


def test_instance_creation_fee_due():
    fd = FeeDue(
        student_id=1, academic_year_id=1, fee_structure_id=1,
        original_amount=50000, amount_paid=0, status="unpaid",
    )
    assert fd.original_amount == 50000
    assert fd.amount_paid == 0
    assert fd.status == "unpaid"


def test_instance_creation_payment():
    p = Payment(
        student_id=1, fee_due_id=1, amount=25000,
        payment_method="cash", receipt_number="RCP001",
    )
    assert p.amount == 25000
    assert p.payment_method == "cash"
    assert p.receipt_number == "RCP001"


@pytest.mark.asyncio
async def test_timestamps_set_on_create(db_session):
    ft = FeeType(name="Test Time", status="active")
    db_session.add(ft)
    await db_session.flush()
    await db_session.refresh(ft)
    assert ft.created_at is not None
    assert ft.updated_at is not None