"""Case, examination and trend routes, the same for v1 and v2.

The two versions differ only in the repository they receive: v1 gets the demo
workspace, and v2 gets the signed-in user's (REQ-P07-S04-002).
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends

from src.api.analysis_flow import analysis_response
from src.api.schemas import (
    API_VERSION,
    AnalysisResponse,
    CaseCreate,
    CaseListResponse,
    CaseResponse,
    ComparisonResponse,
    DeleteResponse,
    ExaminationCreate,
    ExaminationResponse,
    TrendResponse,
)
from src.api.service import ServiceState
from src.longitudinal.comparison import CompatibilityPolicy, MeasurementPoint, compare
from src.longitudinal.records import AnalysisRecord, CaseRecord, ExaminationRecord
from src.longitudinal.trends import build_trend
from src.storage.repository import Repository


def _point(db: Repository, analysis: AnalysisRecord) -> MeasurementPoint:
    if analysis.examination_id is None:
        examination = ExaminationRecord.create(examination_id=f"unlinked-{analysis.analysis_id}")
    else:
        examination = db.get_examination(analysis.examination_id)
    if examination.case_id is None:
        case = CaseRecord.create(case_id="case-unknown")
    else:
        case = db.get_case(examination.case_id)
    return MeasurementPoint(case, examination, analysis)


def router(state: ServiceState, version: str, current_repository: Callable[..., Repository]) -> APIRouter:
    routes = APIRouter(prefix=f"/api/{version}")

    @routes.post("/cases", response_model=CaseResponse, status_code=201)
    def create_case(body: CaseCreate, db: Repository = Depends(current_repository)):
        case = db.add_case(CaseRecord.create(**body.model_dump()))
        return CaseResponse(api_version=version, case=case.to_dict(), examinations=[])

    @routes.get("/cases", response_model=CaseListResponse)
    def list_cases(db: Repository = Depends(current_repository)):
        return CaseListResponse(api_version=version, cases=[case.to_dict() for case in db.list_cases()])

    @routes.get("/cases/{case_id}", response_model=CaseResponse)
    def get_case(case_id: str, db: Repository = Depends(current_repository)):
        case = db.get_case(case_id)
        return CaseResponse(api_version=version, case=case.to_dict(),
                            examinations=[e.to_dict() for e in db.list_examinations(case_id)])

    @routes.delete("/cases/{case_id}", response_model=DeleteResponse)
    def delete_case(case_id: str, db: Repository = Depends(current_repository)):
        return DeleteResponse(api_version=version, deleted={"case_id": case_id, **db.delete_case(case_id, state.blobs)})

    @routes.post("/cases/{case_id}/examinations", response_model=ExaminationResponse, status_code=201)
    def create_examination(case_id: str, body: ExaminationCreate, db: Repository = Depends(current_repository)):
        db.get_case(case_id)
        examination = db.add_examination(ExaminationRecord.create(case_id=case_id, **body.model_dump()))
        return ExaminationResponse(api_version=version, examination=examination.to_dict(), analyses=[])

    @routes.get("/examinations/{examination_id}", response_model=ExaminationResponse)
    def get_examination(examination_id: str, db: Repository = Depends(current_repository)):
        examination = db.get_examination(examination_id)
        analyses = [analysis_response(a, db.get_image(a.image_id).to_dict(), version).model_dump(mode="json")
                    for a in db.list_analyses(examination_id)]
        return ExaminationResponse(api_version=version, examination=examination.to_dict(), analyses=analyses)

    if version == API_VERSION:  # v2 has its own route, which also reports a job in progress
        @routes.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
        def get_analysis(analysis_id: str, db: Repository = Depends(current_repository)):
            record = db.get_analysis(analysis_id)
            return analysis_response(record, db.get_image(record.image_id).to_dict(), version)

    @routes.get("/cases/{case_id}/trend", response_model=TrendResponse)
    def trend(case_id: str, db: Repository = Depends(current_repository)):
        case = db.get_case(case_id)
        pairs = db.latest_analysis_per_examination(case_id)
        result = build_trend([MeasurementPoint(case, e, a) for e, a in pairs], CompatibilityPolicy()).to_dict()
        analysed = {e.examination_id for e, _ in pairs}
        for examination in db.list_examinations(case_id):
            if examination.examination_id not in analysed:
                result["excluded"].append({"examination_id": examination.examination_id, "analysis_id": None,
                                           "reason_codes": ["NO_ANALYSIS"]})
        return TrendResponse(api_version=version, trend=result)

    @routes.get("/compare", response_model=ComparisonResponse)
    def compare_analyses(analysis_a: str, analysis_b: str, db: Repository = Depends(current_repository)):
        a, b = db.get_analysis(analysis_a), db.get_analysis(analysis_b)
        return ComparisonResponse(api_version=version,
                                  comparison=compare(_point(db, a), _point(db, b), CompatibilityPolicy()).to_dict())

    return routes
