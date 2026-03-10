"""Tests for C-MOVE SCU."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydicom import Dataset

from healthcarecli.dicom.connections import AEProfile
from healthcarecli.dicom.move import DicomMoveError, MoveResult, _build_identifier, cmove


def _make_profile(**kwargs):
    defaults = dict(name="test", host="127.0.0.1", port=4242, ae_title="TEST")
    defaults.update(kwargs)
    return AEProfile(**defaults)


def _status(code: int, completed: int = 0, failed: int = 0, warning: int = 0):
    s = Dataset()
    s.Status = code
    s.NumberOfCompletedSuboperations = completed
    s.NumberOfFailedSuboperations = failed
    s.NumberOfWarningSuboperations = warning
    s.NumberOfRemainingSuboperations = 0
    return s


def _mock_assoc(statuses, established: bool = True):
    assoc = MagicMock()
    assoc.is_established = established
    # send_c_move returns an iterator of (status, identifier) tuples
    assoc.send_c_move.return_value = [(s, None) for s in statuses]
    return assoc


# ── _build_identifier ─────────────────────────────────────────────────────────


def test_build_identifier_study_level():
    ds = _build_identifier("1.2.3", "", "")
    assert ds.QueryRetrieveLevel == "STUDY"
    assert ds.StudyInstanceUID == "1.2.3"
    assert not hasattr(ds, "SeriesInstanceUID")


def test_build_identifier_series_level():
    ds = _build_identifier("1.2.3", "4.5.6", "")
    assert ds.QueryRetrieveLevel == "SERIES"
    assert ds.SeriesInstanceUID == "4.5.6"


def test_build_identifier_image_level():
    ds = _build_identifier("1.2.3", "4.5.6", "7.8.9")
    assert ds.QueryRetrieveLevel == "IMAGE"
    assert ds.SOPInstanceUID == "7.8.9"


# ── MoveResult ────────────────────────────────────────────────────────────────


def test_move_result_success_when_status_0000_no_failures():
    r = MoveResult(status_code=0x0000, failed=0)
    assert r.success is True


def test_move_result_failure_when_status_not_0000():
    r = MoveResult(status_code=0xA702, failed=0)
    assert r.success is False


def test_move_result_failure_when_has_failed_subops():
    r = MoveResult(status_code=0x0000, failed=1)
    assert r.success is False


# ── cmove ──────────────────────────────────────────────────────────────────────


@patch("healthcarecli.dicom.move.AE")
def test_cmove_success(mock_ae_cls):
    final_status = _status(0x0000, completed=5)
    assoc = _mock_assoc([_status(0xFF00, completed=3), final_status])
    mock_ae_cls.return_value.associate.return_value = assoc

    result = cmove(_make_profile(), "DEST_AE", study_uid="1.2.3")

    assert result.success is True
    assert result.status_code == 0x0000
    assert result.completed == 5
    assoc.release.assert_called_once()


@patch("healthcarecli.dicom.move.AE")
def test_cmove_raises_without_study_uid(mock_ae_cls):
    with pytest.raises(DicomMoveError, match="study_uid is required"):
        cmove(_make_profile(), "DEST_AE", study_uid="")


@patch("healthcarecli.dicom.move.AE")
def test_cmove_raises_on_no_association(mock_ae_cls):
    assoc = _mock_assoc([], established=False)
    mock_ae_cls.return_value.associate.return_value = assoc

    with pytest.raises(DicomMoveError, match="Could not associate"):
        cmove(_make_profile(), "DEST_AE", study_uid="1.2.3")


@patch("healthcarecli.dicom.move.AE")
def test_cmove_raises_on_none_status(mock_ae_cls):
    assoc = MagicMock()
    assoc.is_established = True
    assoc.send_c_move.return_value = [(None, None)]
    mock_ae_cls.return_value.associate.return_value = assoc

    with pytest.raises(DicomMoveError, match="timed out"):
        cmove(_make_profile(), "DEST_AE", study_uid="1.2.3")


@patch("healthcarecli.dicom.move.AE")
def test_cmove_raises_on_failure_status(mock_ae_cls):
    assoc = _mock_assoc([_status(0xA702)])
    mock_ae_cls.return_value.associate.return_value = assoc

    with pytest.raises(DicomMoveError, match="C-MOVE failed"):
        cmove(_make_profile(), "DEST_AE", study_uid="1.2.3")


@patch("healthcarecli.dicom.move.AE")
def test_cmove_releases_on_failure(mock_ae_cls):
    assoc = _mock_assoc([_status(0xA702)])
    mock_ae_cls.return_value.associate.return_value = assoc

    with pytest.raises(DicomMoveError):
        cmove(_make_profile(), "DEST_AE", study_uid="1.2.3")

    assoc.release.assert_called_once()


@patch("healthcarecli.dicom.move.AE")
def test_cmove_uses_patient_model(mock_ae_cls):
    final_status = _status(0x0000, completed=1)
    assoc = _mock_assoc([final_status])
    mock_ae_cls.return_value.associate.return_value = assoc

    result = cmove(_make_profile(), "DEST", study_uid="1.2.3", model="PATIENT")

    assert result.success is True
    # Verify the AE requested PatientRoot context (not StudyRoot)
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove

    mock_ae_cls.return_value.add_requested_context.assert_called_with(
        PatientRootQueryRetrieveInformationModelMove
    )
