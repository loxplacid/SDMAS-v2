from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _admin_headers(api_client: AsyncClient) -> dict:
    """Login as the seeded admin user (see conftest api_client fixture)."""
    resp = await api_client.post(
        "/auth/login",
        json={"login": "admin", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_fee_type(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.post("/api/fees/fee-types", json={"name": "Tuition"}, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Tuition"
    assert data["status"] == "active"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_fee_type_duplicate(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    await api_client.post("/api/fees/fee-types", json={"name": "Library Fee"}, headers=headers)
    response = await api_client.post("/api/fees/fee-types", json={"name": "Library Fee"}, headers=headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_fee_type_empty_name(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.post("/api/fees/fee-types", json={"name": ""}, headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_fee_type(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    create_resp = await api_client.post("/api/fees/fee-types", json={"name": "Sports Fee"}, headers=headers)
    ft_id = create_resp.json()["id"]
    response = await api_client.get(f"/api/fees/fee-types/{ft_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Sports Fee"


@pytest.mark.asyncio
async def test_get_fee_type_not_found(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/api/fees/fee-types/999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_fee_types(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    await api_client.post("/api/fees/fee-types", json={"name": "Type A"}, headers=headers)
    await api_client.post("/api/fees/fee-types", json={"name": "Type B"}, headers=headers)
    response = await api_client.get("/api/fees/fee-types", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_update_fee_type(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    create_resp = await api_client.post("/api/fees/fee-types", json={"name": "Old Name"}, headers=headers)
    ft_id = create_resp.json()["id"]
    response = await api_client.patch(f"/api/fees/fee-types/{ft_id}", json={"name": "New Name"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_fee_type_not_found(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.patch("/api/fees/fee-types/999", json={"name": "Nope"}, headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_deactivate_fee_type(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    create_resp = await api_client.post("/api/fees/fee-types", json={"name": "Deactivate Me"}, headers=headers)
    ft_id = create_resp.json()["id"]
    response = await api_client.post(f"/api/fees/fee-types/{ft_id}/deactivate", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "inactive"


# ---------------------------------------------------------------------------
# Fee Structure tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_fee_structure(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "Struct Type"}, headers=headers)
    ft = ft_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "FS API Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 10", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()

    response = await api_client.post(
        "/api/fees/structures",
        json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 50000
    assert data["frequency"] == "annual"


@pytest.mark.asyncio
async def test_get_fee_structure(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "Get Struct FT"}, headers=headers)
    ft = ft_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "FS Get Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 11", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    create_resp = await api_client.post(
        "/api/fees/structures",
        json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 30000},
        headers=headers,
    )
    fs_id = create_resp.json()["id"]
    response = await api_client.get(f"/api/fees/structures/{fs_id}", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_fee_structures(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/api/fees/structures", headers=headers)
    assert response.status_code == 200
    assert "items" in response.json()


# ---------------------------------------------------------------------------
# Fee Due tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_fee_dues(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s_resp = await api_client.post("/students", json={"first_name": "Due", "last_name": "Student", "student_number": "FDAPI001"}, headers=headers)
    s = s_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "FD Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 12", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()

    await api_client.post("/api/enrollments", json={"student_id": s["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)

    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "FD Type"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)

    response = await api_client.post(f"/api/fees/dues?student_id={s['id']}&academic_year_id={year['id']}", headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert len(data) >= 1
    assert data[0]["status"] == "unpaid"
    assert data[0]["amount_paid"] == 0


@pytest.mark.asyncio
async def test_get_fee_due(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s_resp = await api_client.post("/students", json={"first_name": "GetDue", "last_name": "Student", "student_number": "FDAPI002"}, headers=headers)
    s = s_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "FD Year 2", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 9", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    await api_client.post("/api/enrollments", json={"student_id": s["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "GetDue FT"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)
    create_resp = await api_client.post(f"/api/fees/dues?student_id={s['id']}&academic_year_id={year['id']}", headers=headers)
    due_id = create_resp.json()[0]["id"]
    response = await api_client.get(f"/api/fees/dues/{due_id}", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_fee_due_not_found(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/api/fees/dues/999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_fee_dues(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/api/fees/dues", headers=headers)
    assert response.status_code == 200
    assert "items" in response.json()


# ---------------------------------------------------------------------------
# Payment tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_payment(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s_resp = await api_client.post("/students", json={"first_name": "Pay", "last_name": "Student", "student_number": "PAYAPI001"}, headers=headers)
    s = s_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "Pay Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 8", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    await api_client.post("/api/enrollments", json={"student_id": s["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "Pay FT"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)
    due_resp = await api_client.post(f"/api/fees/dues?student_id={s['id']}&academic_year_id={year['id']}", headers=headers)
    due_id = due_resp.json()[0]["id"]

    response = await api_client.post(
        "/api/fees/payments",
        json={"student_id": s["id"], "fee_due_id": due_id, "amount": 50000, "receipt_number": "RCP_API001"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "payment" in data
    assert "fee_due" in data
    assert data["fee_due"]["status"] == "paid"


@pytest.mark.asyncio
async def test_record_payment_partial(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s_resp = await api_client.post("/students", json={"first_name": "Partial", "last_name": "Pay", "student_number": "PAYAPI002"}, headers=headers)
    s = s_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "Part Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 7", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    await api_client.post("/api/enrollments", json={"student_id": s["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "Part FT"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)
    due_resp = await api_client.post(f"/api/fees/dues?student_id={s['id']}&academic_year_id={year['id']}", headers=headers)
    due_id = due_resp.json()[0]["id"]

    response = await api_client.post(
        "/api/fees/payments",
        json={"student_id": s["id"], "fee_due_id": due_id, "amount": 20000, "receipt_number": "RCP_PART"},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["fee_due"]["status"] == "partially_paid"


@pytest.mark.asyncio
async def test_record_payment_overpayment(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s_resp = await api_client.post("/students", json={"first_name": "Over", "last_name": "Pay", "student_number": "PAYAPI003"}, headers=headers)
    s = s_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "Over Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 6", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    await api_client.post("/api/enrollments", json={"student_id": s["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "Over FT"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)
    due_resp = await api_client.post(f"/api/fees/dues?student_id={s['id']}&academic_year_id={year['id']}", headers=headers)
    due_id = due_resp.json()[0]["id"]

    response = await api_client.post(
        "/api/fees/payments",
        json={"student_id": s["id"], "fee_due_id": due_id, "amount": 60000, "receipt_number": "RCP_OVER"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_record_payment_duplicate_receipt(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s_resp = await api_client.post("/students", json={"first_name": "Dup", "last_name": "Receipt", "student_number": "PAYAPI004"}, headers=headers)
    s = s_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "Dup Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 5", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    await api_client.post("/api/enrollments", json={"student_id": s["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "Dup FT"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)
    due_resp = await api_client.post(f"/api/fees/dues?student_id={s['id']}&academic_year_id={year['id']}", headers=headers)
    dues = due_resp.json()
    due_id_1 = dues[0]["id"]

    await api_client.post(
        "/api/fees/payments",
        json={"student_id": s["id"], "fee_due_id": due_id_1, "amount": 10000, "receipt_number": "RCP_DUP"},
        headers=headers,
    )
    response = await api_client.post(
        "/api/fees/payments",
        json={"student_id": s["id"], "fee_due_id": due_id_1, "amount": 5000, "receipt_number": "RCP_DUP"},
        headers=headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_payment(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s_resp = await api_client.post("/students", json={"first_name": "GetPay", "last_name": "Student", "student_number": "PAYAPI005"}, headers=headers)
    s = s_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "GetP Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 4", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    await api_client.post("/api/enrollments", json={"student_id": s["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "GetP FT"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)
    due_resp = await api_client.post(f"/api/fees/dues?student_id={s['id']}&academic_year_id={year['id']}", headers=headers)
    due_id = due_resp.json()[0]["id"]
    pmt_resp = await api_client.post(
        "/api/fees/payments",
        json={"student_id": s["id"], "fee_due_id": due_id, "amount": 50000, "receipt_number": "RCP_GETP"},
        headers=headers,
    )
    pmt_id = pmt_resp.json()["payment"]["id"]
    response = await api_client.get(f"/api/fees/payments/{pmt_id}", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_payment_not_found(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/api/fees/payments/999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_payments(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/api/fees/payments", headers=headers)
    assert response.status_code == 200
    assert "items" in response.json()


@pytest.mark.asyncio
async def test_get_payment_by_receipt_number(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s_resp = await api_client.post("/students", json={"first_name": "ByR", "last_name": "Student", "student_number": "PAYAPI006"}, headers=headers)
    s = s_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "ByR Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 3", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    await api_client.post("/api/enrollments", json={"student_id": s["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "ByR FT"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)
    due_resp = await api_client.post(f"/api/fees/dues?student_id={s['id']}&academic_year_id={year['id']}", headers=headers)
    due_id = due_resp.json()[0]["id"]
    await api_client.post(
        "/api/fees/payments",
        json={"student_id": s["id"], "fee_due_id": due_id, "amount": 25000, "receipt_number": "RCP_BYR_API"},
        headers=headers,
    )
    response = await api_client.get("/api/fees/payments/by-receipt/RCP_BYR_API", headers=headers)
    assert response.status_code == 200
    assert response.json()["receipt_number"] == "RCP_BYR_API"


@pytest.mark.asyncio
async def test_get_payment_by_receipt_not_found(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/api/fees/payments/by-receipt/NONEXISTENT", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_student_financial_summary(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s_resp = await api_client.post("/students", json={"first_name": "Sum", "last_name": "Student", "student_number": "SUMAPI001"}, headers=headers)
    s = s_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "Sum Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 2", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    await api_client.post("/api/enrollments", json={"student_id": s["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "Sum FT"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)
    await api_client.post(f"/api/fees/dues?student_id={s['id']}&academic_year_id={year['id']}", headers=headers)

    response = await api_client.get(f"/api/fees/students/{s['id']}/summary?academic_year_id={year['id']}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_fees_assigned" in data
    assert "total_paid" in data
    assert data["total_fees_assigned"] >= 50000


@pytest.mark.asyncio
async def test_class_financial_summary(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s1_resp = await api_client.post("/students", json={"first_name": "ClassA", "last_name": "Student", "student_number": "SUMAPI002"}, headers=headers)
    s1 = s1_resp.json()
    s2_resp = await api_client.post("/students", json={"first_name": "ClassB", "last_name": "Student", "student_number": "SUMAPI003"}, headers=headers)
    s2 = s2_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "Class Sum Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 1", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    await api_client.post("/api/enrollments", json={"student_id": s1["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    await api_client.post("/api/enrollments", json={"student_id": s2["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "Class Sum FT"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)
    await api_client.post(f"/api/fees/dues?student_id={s1['id']}&academic_year_id={year['id']}", headers=headers)
    await api_client.post(f"/api/fees/dues?student_id={s2['id']}&academic_year_id={year['id']}", headers=headers)

    response = await api_client.get(f"/api/fees/classes/{cls['id']}/summary?academic_year_id={year['id']}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_students"] == 2
    assert data["total_fees_assigned"] >= 100000


@pytest.mark.asyncio
async def test_student_fees_endpoint(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    s_resp = await api_client.post("/students", json={"first_name": "Stud", "last_name": "Fees", "student_number": "SFAPI001"}, headers=headers)
    s = s_resp.json()
    year_resp = await api_client.post("/api/academic-years", json={"name": "SF Year", "start_date": "2026-01-01", "end_date": "2026-12-31"}, headers=headers)
    year = year_resp.json()
    cls_resp = await api_client.post("/api/classes", json={"name": "Grade 1B", "academic_year_id": year["id"]}, headers=headers)
    cls = cls_resp.json()
    await api_client.post("/api/enrollments", json={"student_id": s["id"], "academic_year_id": year["id"], "class_id": cls["id"]}, headers=headers)
    ft_resp = await api_client.post("/api/fees/fee-types", json={"name": "SF FT"}, headers=headers)
    ft = ft_resp.json()
    await api_client.post("/api/fees/structures", json={"academic_year_id": year["id"], "class_id": cls["id"], "fee_type_id": ft["id"], "amount": 50000}, headers=headers)

    response = await api_client.get(f"/api/fees/students/{s['id']}/fees?academic_year_id={year['id']}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["fee_type_name"] == "SF FT"


@pytest.mark.asyncio
async def test_health_still_works(api_client: AsyncClient):
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
