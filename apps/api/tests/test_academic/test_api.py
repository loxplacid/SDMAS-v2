from __future__ import annotations

import pytest
from httpx import AsyncClient


# ===========================================================================
# Academic Year API
# ===========================================================================

class TestAcademicYearAPI:
    CREATE_PAYLOAD = {
        "name": "2026-2027",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
    }

    @pytest.mark.asyncio
    async def test_create(self, api_client: AsyncClient):
        resp = await api_client.post("/api/academic-years", json=self.CREATE_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "2026-2027"
        assert data["status"] == "active"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_duplicate(self, api_client: AsyncClient):
        await api_client.post("/api/academic-years", json=self.CREATE_PAYLOAD)
        resp = await api_client.post("/api/academic-years", json=self.CREATE_PAYLOAD)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_get(self, api_client: AsyncClient):
        create_resp = await api_client.post("/api/academic-years", json=self.CREATE_PAYLOAD)
        year_id = create_resp.json()["id"]
        resp = await api_client.get(f"/api/academic-years/{year_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "2026-2027"

    @pytest.mark.asyncio
    async def test_get_not_found(self, api_client: AsyncClient):
        resp = await api_client.get("/api/academic-years/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list(self, api_client: AsyncClient):
        await api_client.post("/api/academic-years", json=self.CREATE_PAYLOAD)
        resp = await api_client.get("/api/academic-years")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_pagination(self, api_client: AsyncClient):
        for i in range(3):
            await api_client.post(
                "/api/academic-years",
                json={
                    "name": f"Year {i}",
                    "start_date": f"2026-0{i+1}-01",
                    "end_date": f"2026-12-31",
                },
            )
        resp = await api_client.get("/api/academic-years?page=1&size=2")
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_update(self, api_client: AsyncClient):
        create_resp = await api_client.post("/api/academic-years", json=self.CREATE_PAYLOAD)
        year_id = create_resp.json()["id"]
        resp = await api_client.patch(
            f"/api/academic-years/{year_id}", json={"name": "2027-2028"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "2027-2028"

    @pytest.mark.asyncio
    async def test_delete(self, api_client: AsyncClient):
        create_resp = await api_client.post("/api/academic-years", json=self.CREATE_PAYLOAD)
        year_id = create_resp.json()["id"]
        resp = await api_client.delete(f"/api/academic-years/{year_id}")
        assert resp.status_code == 204
        get_resp = await api_client.get(f"/api/academic-years/{year_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_payload(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/api/academic-years",
            json={"name": "", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        assert resp.status_code == 422


# ===========================================================================
# Class API
# ===========================================================================

class TestClassAPI:
    @pytest.mark.asyncio
    async def test_create(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "AY1", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]

        resp = await api_client.post(
            "/api/classes", json={"name": "Grade 10", "academic_year_id": year_id}
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Grade 10"

    @pytest.mark.asyncio
    async def test_create_duplicate(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "AY2", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        await api_client.post(
            "/api/classes", json={"name": "Grade 10", "academic_year_id": year_id}
        )
        resp = await api_client.post(
            "/api/classes", json={"name": "Grade 10", "academic_year_id": year_id}
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_by_year(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "AY3", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        await api_client.post(
            "/api/classes", json={"name": "Grade 10", "academic_year_id": year_id}
        )
        resp = await api_client.get(f"/api/classes?academic_year_id={year_id}")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_update(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "AY4", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes", json={"name": "Grade 10", "academic_year_id": year_id}
        )
        class_id = c_resp.json()["id"]
        resp = await api_client.patch(
            f"/api/classes/{class_id}", json={"name": "Grade 11"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Grade 11"

    @pytest.mark.asyncio
    async def test_delete(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "AY5", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes", json={"name": "Grade 10", "academic_year_id": year_id}
        )
        class_id = c_resp.json()["id"]
        resp = await api_client.delete(f"/api/classes/{class_id}")
        assert resp.status_code == 204


# ===========================================================================
# Section API
# ===========================================================================

class TestSectionAPI:
    @pytest.mark.asyncio
    async def test_create(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "SY1", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes", json={"name": "Grade 10", "academic_year_id": year_id}
        )
        class_id = c_resp.json()["id"]

        resp = await api_client.post(
            "/api/sections", json={"name": "A", "class_id": class_id}
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "A"

    @pytest.mark.asyncio
    async def test_list_by_class(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "SY2", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes", json={"name": "Grade 10", "academic_year_id": year_id}
        )
        class_id = c_resp.json()["id"]
        await api_client.post("/api/sections", json={"name": "A", "class_id": class_id})

        resp = await api_client.get(f"/api/sections?class_id={class_id}")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_delete(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "SY3", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes", json={"name": "Grade 10", "academic_year_id": year_id}
        )
        class_id = c_resp.json()["id"]
        s_resp = await api_client.post(
            "/api/sections", json={"name": "A", "class_id": class_id}
        )
        section_id = s_resp.json()["id"]

        resp = await api_client.delete(f"/api/sections/{section_id}")
        assert resp.status_code == 204


# ===========================================================================
# Enrollment API
# ===========================================================================

class TestEnrollmentAPI:
    @pytest.mark.asyncio
    async def test_create(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "EY1", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        student_resp = await api_client.post(
            "/students",
            json={
                "first_name": "Enroll",
                "last_name": "Student",
                "student_number": "ENRAPI001",
            },
        )
        student_id = student_resp.json()["id"]

        resp = await api_client.post(
            "/api/enrollments",
            json={"student_id": student_id, "academic_year_id": year_id},
        )
        assert resp.status_code == 201
        assert resp.json()["student_id"] == student_id
        assert resp.json()["academic_year_id"] == year_id

    @pytest.mark.asyncio
    async def test_create_with_class_and_section(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "EY2", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes", json={"name": "Grade 10", "academic_year_id": year_id}
        )
        class_id = c_resp.json()["id"]
        s_resp = await api_client.post(
            "/api/sections", json={"name": "A", "class_id": class_id}
        )
        section_id = s_resp.json()["id"]
        student_resp = await api_client.post(
            "/students",
            json={
                "first_name": "Enroll2",
                "last_name": "Student",
                "student_number": "ENRAPI002",
            },
        )
        student_id = student_resp.json()["id"]

        resp = await api_client.post(
            "/api/enrollments",
            json={
                "student_id": student_id,
                "academic_year_id": year_id,
                "class_id": class_id,
                "section_id": section_id,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["class_id"] == class_id
        assert resp.json()["section_id"] == section_id

    @pytest.mark.asyncio
    async def test_duplicate_enrollment(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "EY3", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        student_resp = await api_client.post(
            "/students",
            json={
                "first_name": "Dup",
                "last_name": "Student",
                "student_number": "ENRAPI003",
            },
        )
        student_id = student_resp.json()["id"]
        payload = {"student_id": student_id, "academic_year_id": year_id}
        await api_client.post("/api/enrollments", json=payload)
        resp = await api_client.post("/api/enrollments", json=payload)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_get_enrollment(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "EY4", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        student_resp = await api_client.post(
            "/students",
            json={
                "first_name": "Get",
                "last_name": "Enroll",
                "student_number": "ENRAPI004",
            },
        )
        student_id = student_resp.json()["id"]
        e_resp = await api_client.post(
            "/api/enrollments",
            json={"student_id": student_id, "academic_year_id": year_id},
        )
        enrollment_id = e_resp.json()["id"]

        resp = await api_client.get(f"/api/enrollments/{enrollment_id}")
        assert resp.status_code == 200
        assert resp.json()["student_id"] == student_id

    @pytest.mark.asyncio
    async def test_list_enrollments_by_student(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "EY5", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        student_resp = await api_client.post(
            "/students",
            json={
                "first_name": "List",
                "last_name": "Enroll",
                "student_number": "ENRAPI005",
            },
        )
        student_id = student_resp.json()["id"]
        await api_client.post(
            "/api/enrollments",
            json={"student_id": student_id, "academic_year_id": year_id},
        )

        resp = await api_client.get(f"/api/enrollments?student_id={student_id}")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_delete(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={"name": "EY6", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        year_id = year_resp.json()["id"]
        student_resp = await api_client.post(
            "/students",
            json={
                "first_name": "Del",
                "last_name": "Enroll",
                "student_number": "ENRAPI006",
            },
        )
        student_id = student_resp.json()["id"]
        e_resp = await api_client.post(
            "/api/enrollments",
            json={"student_id": student_id, "academic_year_id": year_id},
        )
        enrollment_id = e_resp.json()["id"]

        resp = await api_client.delete(f"/api/enrollments/{enrollment_id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_health_still_works(self, api_client: AsyncClient):
        resp = await api_client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_students_still_work(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/students",
            json={
                "first_name": "Post",
                "last_name": "Academic",
                "student_number": "POSTACAD001",
            },
        )
        assert resp.status_code == 201


# ===========================================================================
# Term API
# ===========================================================================


class TestTermAPI:
    @pytest.mark.asyncio
    async def test_create_term(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={
                "name": "TYear1",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        year_id = year_resp.json()["id"]

        resp = await api_client.post(
            f"/api/academic-years/{year_id}/terms",
            json={
                "name": "Term 1",
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Term 1"
        assert data["academic_year_id"] == year_id

    @pytest.mark.asyncio
    async def test_list_terms(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={
                "name": "TYear2",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        year_id = year_resp.json()["id"]
        await api_client.post(
            f"/api/academic-years/{year_id}/terms",
            json={
                "name": "Term 1",
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
            },
        )
        resp = await api_client.get(f"/api/academic-years/{year_id}/terms")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_term(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={
                "name": "TYear3",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        year_id = year_resp.json()["id"]
        t_resp = await api_client.post(
            f"/api/academic-years/{year_id}/terms",
            json={
                "name": "Term 1",
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
            },
        )
        term_id = t_resp.json()["id"]

        resp = await api_client.get(f"/api/terms/{term_id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_term_not_found(self, api_client: AsyncClient):
        resp = await api_client.get("/api/terms/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_overlapping_terms(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={
                "name": "TYear4",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        year_id = year_resp.json()["id"]
        await api_client.post(
            f"/api/academic-years/{year_id}/terms",
            json={
                "name": "Term 1",
                "start_date": "2026-01-01",
                "end_date": "2026-06-30",
            },
        )
        resp = await api_client.post(
            f"/api/academic-years/{year_id}/terms",
            json={
                "name": "Term 2",
                "start_date": "2026-03-01",
                "end_date": "2026-09-30",
            },
        )
        assert resp.status_code == 409


# ===========================================================================
# Subject API
# ===========================================================================


class TestSubjectAPI:
    @pytest.mark.asyncio
    async def test_create_subject(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/api/subjects",
            json={"name": "Mathematics", "code": "MATH101"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Mathematics"
        assert data["code"] == "MATH101"

    @pytest.mark.asyncio
    async def test_create_duplicate_name(self, api_client: AsyncClient):
        await api_client.post(
            "/api/subjects",
            json={"name": "Science", "code": "SCI101"},
        )
        resp = await api_client.post(
            "/api/subjects",
            json={"name": "Science", "code": "SCI102"},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_get_subject(self, api_client: AsyncClient):
        c_resp = await api_client.post(
            "/api/subjects",
            json={"name": "History", "code": "HIST101"},
        )
        subj_id = c_resp.json()["id"]
        resp = await api_client.get(f"/api/subjects/{subj_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "History"

    @pytest.mark.asyncio
    async def test_get_not_found(self, api_client: AsyncClient):
        resp = await api_client.get("/api/subjects/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_subjects(self, api_client: AsyncClient):
        await api_client.post(
            "/api/subjects", json={"name": "Math", "code": "MATH101"}
        )
        resp = await api_client.get("/api/subjects")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_update_subject(self, api_client: AsyncClient):
        c_resp = await api_client.post(
            "/api/subjects", json={"name": "Math", "code": "MATH101"}
        )
        subj_id = c_resp.json()["id"]
        resp = await api_client.patch(
            f"/api/subjects/{subj_id}", json={"name": "Advanced Math"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Advanced Math"


# ===========================================================================
# Teacher API
# ===========================================================================


class TestTeacherAPI:
    @pytest.mark.asyncio
    async def test_create_teacher(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/api/teachers",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "employee_number": "TCH001",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["first_name"] == "John"
        assert data["employee_number"] == "TCH001"

    @pytest.mark.asyncio
    async def test_create_duplicate_employee_number(
        self, api_client: AsyncClient
    ):
        await api_client.post(
            "/api/teachers",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "employee_number": "TCH002",
            },
        )
        resp = await api_client.post(
            "/api/teachers",
            json={
                "first_name": "Jane",
                "last_name": "Smith",
                "employee_number": "TCH002",
            },
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_get_teacher(self, api_client: AsyncClient):
        c_resp = await api_client.post(
            "/api/teachers",
            json={
                "first_name": "Jane",
                "last_name": "Smith",
                "employee_number": "TCH003",
            },
        )
        teacher_id = c_resp.json()["id"]
        resp = await api_client.get(f"/api/teachers/{teacher_id}")
        assert resp.status_code == 200
        assert resp.json()["first_name"] == "Jane"

    @pytest.mark.asyncio
    async def test_get_not_found(self, api_client: AsyncClient):
        resp = await api_client.get("/api/teachers/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_teachers(self, api_client: AsyncClient):
        await api_client.post(
            "/api/teachers",
            json={
                "first_name": "A",
                "last_name": "B",
                "employee_number": "TCH010",
            },
        )
        resp = await api_client.get("/api/teachers")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_update_teacher(self, api_client: AsyncClient):
        c_resp = await api_client.post(
            "/api/teachers",
            json={
                "first_name": "Orig",
                "last_name": "Name",
                "employee_number": "TCH020",
            },
        )
        teacher_id = c_resp.json()["id"]
        resp = await api_client.patch(
            f"/api/teachers/{teacher_id}", json={"first_name": "Updated"}
        )
        assert resp.status_code == 200
        assert resp.json()["first_name"] == "Updated"


# ===========================================================================
# TeacherAssignment API
# ===========================================================================


class TestTeacherAssignmentAPI:
    @pytest.mark.asyncio
    async def test_assign_teacher(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={
                "name": "AYAssign1",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes",
            json={"name": "Grade 10", "academic_year_id": year_id},
        )
        class_id = c_resp.json()["id"]
        t_resp = await api_client.post(
            "/api/teachers",
            json={
                "first_name": "Assign",
                "last_name": "Teacher",
                "employee_number": "ASN001",
            },
        )
        teacher_id = t_resp.json()["id"]
        s_resp = await api_client.post(
            "/api/subjects",
            json={"name": "Algebra", "code": "ALG101"},
        )
        subject_id = s_resp.json()["id"]

        resp = await api_client.post(
            "/api/teacher-assignments",
            json={
                "teacher_id": teacher_id,
                "class_id": class_id,
                "subject_id": subject_id,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["teacher_id"] == teacher_id
        assert data["class_id"] == class_id

    @pytest.mark.asyncio
    async def test_assign_without_subject(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={
                "name": "AYAssign2",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes",
            json={"name": "Grade 11", "academic_year_id": year_id},
        )
        class_id = c_resp.json()["id"]
        t_resp = await api_client.post(
            "/api/teachers",
            json={
                "first_name": "NoSubject",
                "last_name": "Teacher",
                "employee_number": "ASN002",
            },
        )
        teacher_id = t_resp.json()["id"]

        resp = await api_client.post(
            "/api/teacher-assignments",
            json={
                "teacher_id": teacher_id,
                "class_id": class_id,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["subject_id"] is None

    @pytest.mark.asyncio
    async def test_get_assignment(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={
                "name": "AYAssign3",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes",
            json={"name": "Grade 10", "academic_year_id": year_id},
        )
        class_id = c_resp.json()["id"]
        t_resp = await api_client.post(
            "/api/teachers",
            json={
                "first_name": "Get",
                "last_name": "Assign",
                "employee_number": "ASN003",
            },
        )
        teacher_id = t_resp.json()["id"]
        a_resp = await api_client.post(
            "/api/teacher-assignments",
            json={"teacher_id": teacher_id, "class_id": class_id},
        )
        assignment_id = a_resp.json()["id"]

        resp = await api_client.get(
            f"/api/teacher-assignments/{assignment_id}"
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_assignment_not_found(self, api_client: AsyncClient):
        resp = await api_client.get("/api/teacher-assignments/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_by_class(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={
                "name": "AYAssign4",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes",
            json={"name": "Grade 10", "academic_year_id": year_id},
        )
        class_id = c_resp.json()["id"]
        t_resp = await api_client.post(
            "/api/teachers",
            json={
                "first_name": "List",
                "last_name": "Assign",
                "employee_number": "ASN004",
            },
        )
        teacher_id = t_resp.json()["id"]
        await api_client.post(
            "/api/teacher-assignments",
            json={"teacher_id": teacher_id, "class_id": class_id},
        )

        resp = await api_client.get(
            f"/api/teacher-assignments?class_id={class_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_unassign(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={
                "name": "AYAssign5",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes",
            json={"name": "Grade 10", "academic_year_id": year_id},
        )
        class_id = c_resp.json()["id"]
        t_resp = await api_client.post(
            "/api/teachers",
            json={
                "first_name": "Delete",
                "last_name": "Assign",
                "employee_number": "ASN005",
            },
        )
        teacher_id = t_resp.json()["id"]
        a_resp = await api_client.post(
            "/api/teacher-assignments",
            json={"teacher_id": teacher_id, "class_id": class_id},
        )
        assignment_id = a_resp.json()["id"]

        resp = await api_client.delete(
            f"/api/teacher-assignments/{assignment_id}"
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_duplicate_assignment(self, api_client: AsyncClient):
        year_resp = await api_client.post(
            "/api/academic-years",
            json={
                "name": "AYAssign6",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        year_id = year_resp.json()["id"]
        c_resp = await api_client.post(
            "/api/classes",
            json={"name": "Grade 10", "academic_year_id": year_id},
        )
        class_id = c_resp.json()["id"]
        t_resp = await api_client.post(
            "/api/teachers",
            json={
                "first_name": "Dup",
                "last_name": "Assign",
                "employee_number": "ASN006",
            },
        )
        teacher_id = t_resp.json()["id"]
        s_resp = await api_client.post(
            "/api/subjects",
            json={"name": "Geometry", "code": "GEO101"},
        )
        subject_id = s_resp.json()["id"]

        payload = {
            "teacher_id": teacher_id,
            "class_id": class_id,
            "subject_id": subject_id,
        }
        await api_client.post("/api/teacher-assignments", json=payload)
        resp = await api_client.post(
            "/api/teacher-assignments", json=payload
        )
        assert resp.status_code == 409