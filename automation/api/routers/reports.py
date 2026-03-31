from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from automation.api.report_center import (
    build_service_station_flow_report_result,
    export_service_station_flow_report,
    build_person_attributes_history_report_result,
    export_person_attributes_history_report,
    get_report_center_catalog,
    get_person_attributes_history_options,
    get_service_station_flow_options,
    open_report_output_folder,
)

router = APIRouter(prefix="/reports", tags=["reports"])


class ServiceStationFlowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    startDate: date
    endDate: date
    saveAsPath: str = ""


class OpenReportFolderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str


class PersonAttributesHistoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effectiveDate: date
    saveAsPath: str = ""


@router.get("/catalog")
def get_report_catalog() -> dict[str, object]:
    return get_report_center_catalog()


@router.get("/service-station-flow/options")
def get_service_station_flow_report_options() -> dict[str, object]:
    return get_service_station_flow_options()


@router.post("/service-station-flow/query")
def post_service_station_flow_report_query(payload: ServiceStationFlowRequest) -> dict[str, object]:
    try:
        result = build_service_station_flow_report_result(
            start_date=payload.startDate,
            end_date=payload.endDate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        **result,
        "exportInfo": None,
    }


@router.post("/service-station-flow/export")
def post_service_station_flow_report_export(payload: ServiceStationFlowRequest) -> dict[str, object]:
    try:
        return export_service_station_flow_report(
            start_date=payload.startDate,
            end_date=payload.endDate,
            save_as_path=payload.saveAsPath,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/person-attributes-history/options")
def get_person_attributes_history_report_options() -> dict[str, object]:
    return get_person_attributes_history_options()


@router.post("/person-attributes-history/query")
def post_person_attributes_history_report_query(payload: PersonAttributesHistoryRequest) -> dict[str, object]:
    try:
        result = build_person_attributes_history_report_result(
            effective_date=payload.effectiveDate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        **result,
        "exportInfo": None,
    }


@router.post("/person-attributes-history/export")
def post_person_attributes_history_report_export(payload: PersonAttributesHistoryRequest) -> dict[str, object]:
    try:
        return export_person_attributes_history_report(
            effective_date=payload.effectiveDate,
            save_as_path=payload.saveAsPath,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/open-folder")
def post_open_report_folder(payload: OpenReportFolderRequest) -> dict[str, str]:
    try:
        return open_report_output_folder(payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
