"""DICOM C-MOVE SCU — retrieve instances from a PACS to a C-STORE SCP destination."""

from __future__ import annotations

from dataclasses import dataclass

from pynetdicom import AE
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
)
from pynetdicom.status import code_to_category

from healthcarecli.dicom.connections import AEProfile


@dataclass
class MoveResult:
    """Aggregated outcome of a C-MOVE operation."""

    completed: int = 0
    remaining: int = 0
    failed: int = 0
    warning: int = 0
    status_code: int | None = None

    @property
    def success(self) -> bool:
        return self.status_code == 0x0000 and self.failed == 0


class DicomMoveError(RuntimeError):
    pass


def cmove(
    source: AEProfile,
    destination_ae: str,
    *,
    study_uid: str = "",
    series_uid: str = "",
    instance_uid: str = "",
    model: str = "STUDY",
) -> MoveResult:
    """Send a C-MOVE request to *source* PACS, directing it to push instances to
    *destination_ae*.

    Granularity:
        - study_uid only          → move entire study
        - study_uid + series_uid  → move one series
        - all three UIDs          → move single instance

    Args:
        source:         PACS that holds the images.
        destination_ae: AE title of the SCP that should *receive* the images
                        (must be registered in the source PACS move table).
        study_uid:      StudyInstanceUID (required).
        series_uid:     SeriesInstanceUID (optional).
        instance_uid:   SOPInstanceUID (optional).
        model:          "STUDY" (default) or "PATIENT" root query model.

    Returns:
        MoveResult with completion counts and final status code.

    Raises:
        DicomMoveError: on association failure or unrecoverable failure status.
    """
    if not study_uid:
        raise DicomMoveError("study_uid is required for C-MOVE")

    ae = AE(ae_title=source.calling_ae)
    sop_class = (
        StudyRootQueryRetrieveInformationModelMove
        if model.upper() == "STUDY"
        else PatientRootQueryRetrieveInformationModelMove
    )
    ae.add_requested_context(sop_class)

    assoc = ae.associate(source.host, source.port, ae_title=source.ae_title)
    if not assoc.is_established:
        raise DicomMoveError(
            f"Could not associate with {source.ae_title}@{source.host}:{source.port}"
        )

    identifier = _build_identifier(study_uid, series_uid, instance_uid)
    result = MoveResult()

    try:
        responses = assoc.send_c_move(identifier, destination_ae, sop_class)
        for status, _ in responses:
            if status is None:
                raise DicomMoveError("Connection timed out or lost during C-MOVE")

            result.status_code = status.Status
            category = code_to_category(status.Status)

            # Pending responses carry sub-operation counts
            result.completed = getattr(status, "NumberOfCompletedSuboperations", result.completed)
            result.remaining = getattr(status, "NumberOfRemainingSuboperations", result.remaining)
            result.failed = getattr(status, "NumberOfFailedSuboperations", result.failed)
            result.warning = getattr(status, "NumberOfWarningSuboperations", result.warning)

            if category == "Failure":
                raise DicomMoveError(f"C-MOVE failed — status 0x{status.Status:04X}")
    finally:
        assoc.release()

    return result


def _build_identifier(study_uid: str, series_uid: str, instance_uid: str):
    from pydicom import Dataset

    ds = Dataset()
    if instance_uid and series_uid:
        ds.QueryRetrieveLevel = "IMAGE"
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
        ds.SOPInstanceUID = instance_uid
    elif series_uid:
        ds.QueryRetrieveLevel = "SERIES"
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
    else:
        ds.QueryRetrieveLevel = "STUDY"
        ds.StudyInstanceUID = study_uid
    return ds
