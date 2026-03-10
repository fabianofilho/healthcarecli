"""Tests for FHIR R4 client module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

import healthcarecli.config.manager as mgr
from healthcarecli.fhir.client import (
    FHIRAuthError,
    FHIRError,
    FHIRProfile,
    FHIRProfileNotFoundError,
    _raise_for_fhir,
    bundle_entries,
    bundle_total,
    fhir_capabilities,
    fhir_create,
    fhir_delete,
    fhir_get,
    fhir_search,
    fhir_update,
)

# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect config writes to a temp directory for every test."""
    monkeypatch.setattr(mgr, "config_dir", lambda: tmp_path)


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_profile(**kwargs) -> FHIRProfile:
    defaults = dict(name="test", url="https://fhir.example.com/baseR4")
    defaults.update(kwargs)
    return FHIRProfile(**defaults)


def _ok_response(body: dict, status: int = 200) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.ok = status < 400
    resp.status_code = status
    resp.json.return_value = body
    return resp


def _error_response(status: int, body: dict | None = None, reason: str = "Error") -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.ok = False
    resp.status_code = status
    resp.reason = reason
    resp.text = reason
    resp.json.return_value = body or {}
    return resp


# ── FHIRProfile persistence ───────────────────────────────────────────────────


def test_profile_save_and_load():
    p = _make_profile()
    p.save()
    loaded = FHIRProfile.load("test")
    assert loaded.url == "https://fhir.example.com/baseR4"
    assert loaded.auth_type == "none"


def test_profile_load_not_found():
    with pytest.raises(FHIRProfileNotFoundError):
        FHIRProfile.load("nonexistent")


def test_profile_list_all():
    _make_profile(name="a", url="https://a.example.com").save()
    _make_profile(name="b", url="https://b.example.com").save()
    profiles = FHIRProfile.list_all()
    assert len(profiles) == 2
    names = {p.name for p in profiles}
    assert names == {"a", "b"}


def test_profile_delete():
    p = _make_profile()
    p.save()
    p.delete()
    with pytest.raises(FHIRProfileNotFoundError):
        FHIRProfile.load("test")


def test_profile_to_dict_redacts_secrets():
    p = _make_profile(password="secret", token="tok123", client_secret="cs")
    d = p.to_dict()
    assert d["password"] == "***"
    assert d["token"] == "***"
    assert d["client_secret"] == "***"


# ── session auth ──────────────────────────────────────────────────────────────


def test_session_no_auth_has_fhir_headers():
    p = _make_profile()
    s = p.session()
    assert s.headers["Accept"] == "application/fhir+json"
    assert s.headers["Content-Type"] == "application/fhir+json"


def test_session_basic_auth():
    p = _make_profile(auth_type="basic", username="user", password="pass")
    s = p.session()
    assert s.auth is not None


def test_session_bearer_token():
    p = _make_profile(auth_type="bearer", token="mytoken")
    s = p.session()
    assert "Bearer mytoken" in s.headers.get("Authorization", "")


def test_session_bearer_no_token_raises():
    p = _make_profile(auth_type="bearer")
    with pytest.raises(FHIRAuthError):
        p.session()


# ── _raise_for_fhir ───────────────────────────────────────────────────────────


def test_raise_for_fhir_ok_does_nothing():
    resp = _ok_response({"resourceType": "Patient"})
    _raise_for_fhir(resp)  # should not raise


def test_raise_for_fhir_404_raises():
    resp = _error_response(404, reason="Not Found")
    with pytest.raises(FHIRError) as exc_info:
        _raise_for_fhir(resp)
    assert exc_info.value.status_code == 404


def test_raise_for_fhir_operation_outcome():
    body = {
        "resourceType": "OperationOutcome",
        "issue": [{"severity": "error", "diagnostics": "Patient not found"}],
    }
    resp = _error_response(404, body=body)
    with pytest.raises(FHIRError, match="Patient not found"):
        _raise_for_fhir(resp)


# ── bundle helpers ────────────────────────────────────────────────────────────


def test_bundle_entries_extracts_resources():
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "1"}},
            {"resource": {"resourceType": "Patient", "id": "2"}},
            {"search": {"mode": "match"}},  # entry without resource
        ],
    }
    entries = bundle_entries(bundle)
    assert len(entries) == 2
    assert entries[0]["id"] == "1"


def test_bundle_entries_empty_bundle():
    assert bundle_entries({"resourceType": "Bundle"}) == []


def test_bundle_total_present():
    assert bundle_total({"total": 42}) == 42


def test_bundle_total_absent():
    assert bundle_total({}) is None


# ── fhir_search ───────────────────────────────────────────────────────────────


@patch("healthcarecli.fhir.client.requests.Session")
def test_fhir_search_calls_correct_url(mock_session_cls):
    bundle = {"resourceType": "Bundle", "total": 1, "entry": []}
    session = MagicMock()
    session.get.return_value = _ok_response(bundle)
    session.headers = {}
    mock_session_cls.return_value = session

    p = _make_profile()
    with patch.object(p, "session", return_value=session):
        result = fhir_search(p, "Patient", params={"family": "Smith"})

    session.get.assert_called_once()
    call_args = session.get.call_args
    assert "Patient" in call_args[0][0]
    assert result["resourceType"] == "Bundle"


@patch("healthcarecli.fhir.client.requests.Session")
def test_fhir_search_with_count_and_offset(mock_session_cls):
    bundle = {"resourceType": "Bundle", "entry": []}
    session = MagicMock()
    session.get.return_value = _ok_response(bundle)
    session.headers = {}
    mock_session_cls.return_value = session

    p = _make_profile()
    with patch.object(p, "session", return_value=session):
        fhir_search(p, "Patient", count=10, offset=20)

    _, kwargs = session.get.call_args
    params = kwargs.get("params", {})
    assert params.get("_count") == "10"
    assert params.get("_getpagesoffset") == "20"


# ── fhir_get ──────────────────────────────────────────────────────────────────


@patch("healthcarecli.fhir.client.requests.Session")
def test_fhir_get_returns_resource(mock_session_cls):
    patient = {"resourceType": "Patient", "id": "123"}
    session = MagicMock()
    session.get.return_value = _ok_response(patient)
    session.headers = {}
    mock_session_cls.return_value = session

    p = _make_profile()
    with patch.object(p, "session", return_value=session):
        result = fhir_get(p, "Patient", "123")

    assert result["id"] == "123"
    url = session.get.call_args[0][0]
    assert url.endswith("Patient/123")


@patch("healthcarecli.fhir.client.requests.Session")
def test_fhir_get_raises_on_404(mock_session_cls):
    session = MagicMock()
    session.get.return_value = _error_response(404)
    session.headers = {}
    mock_session_cls.return_value = session

    p = _make_profile()
    with patch.object(p, "session", return_value=session):
        with pytest.raises(FHIRError) as exc_info:
            fhir_get(p, "Patient", "missing")
    assert exc_info.value.status_code == 404


# ── fhir_create ───────────────────────────────────────────────────────────────


@patch("healthcarecli.fhir.client.requests.Session")
def test_fhir_create_posts_to_resource_type(mock_session_cls):
    created = {"resourceType": "Patient", "id": "new-id"}
    session = MagicMock()
    session.post.return_value = _ok_response(created, status=201)
    session.headers = {}
    mock_session_cls.return_value = session

    p = _make_profile()
    resource = {"resourceType": "Patient", "name": [{"family": "Doe"}]}
    with patch.object(p, "session", return_value=session):
        result = fhir_create(p, resource)

    assert result["id"] == "new-id"
    url = session.post.call_args[0][0]
    assert url.endswith("Patient")


def test_fhir_create_raises_without_resource_type():
    p = _make_profile()
    session = MagicMock()
    session.headers = {}
    with patch.object(p, "session", return_value=session):
        with pytest.raises(FHIRError, match="resourceType"):
            fhir_create(p, {"name": "no type"})


# ── fhir_update ───────────────────────────────────────────────────────────────


@patch("healthcarecli.fhir.client.requests.Session")
def test_fhir_update_puts_to_correct_url(mock_session_cls):
    updated = {"resourceType": "Patient", "id": "123"}
    session = MagicMock()
    session.put.return_value = _ok_response(updated)
    session.headers = {}
    mock_session_cls.return_value = session

    p = _make_profile()
    with patch.object(p, "session", return_value=session):
        result = fhir_update(p, "Patient", "123", {"resourceType": "Patient"})

    url = session.put.call_args[0][0]
    assert url.endswith("Patient/123")
    assert result["id"] == "123"


# ── fhir_delete ───────────────────────────────────────────────────────────────


@patch("healthcarecli.fhir.client.requests.Session")
def test_fhir_delete_calls_delete_on_correct_url(mock_session_cls):
    session = MagicMock()
    session.delete.return_value = _ok_response({}, status=204)
    session.headers = {}
    mock_session_cls.return_value = session

    p = _make_profile()
    with patch.object(p, "session", return_value=session):
        fhir_delete(p, "Patient", "123")

    url = session.delete.call_args[0][0]
    assert url.endswith("Patient/123")


# ── fhir_capabilities ────────────────────────────────────────────────────────


@patch("healthcarecli.fhir.client.requests.Session")
def test_fhir_capabilities_fetches_metadata(mock_session_cls):
    cap = {"resourceType": "CapabilityStatement", "fhirVersion": "4.0.1"}
    session = MagicMock()
    session.get.return_value = _ok_response(cap)
    session.headers = {}
    mock_session_cls.return_value = session

    p = _make_profile()
    with patch.object(p, "session", return_value=session):
        result = fhir_capabilities(p)

    url = session.get.call_args[0][0]
    assert url.endswith("/metadata")
    assert result["fhirVersion"] == "4.0.1"
