"""The document endpoints of the API.

The upload endpoint is the most demanding one: it accepts an untrusted
payload, therefore it

* reads the file in **bounded chunks** (an upload is never read into the
  memory as a whole) and rejects a file that is larger than the configured
  maximum with ``413``,
* lets the document service validate the payload (the content of the file
  decides whether it is a PDF, the name and the announced MIME type are
  only corroborating signals) and reports the collected issue codes when
  the upload is rejected,
* submits the processing to the job runner and reports the **real** status
  of the document when the request returns.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from pydantic import ValidationError as PydanticValidationError

from app.agents.job_runner import JobRunner
from app.api.deps import (
    CurrentUserDep,
    SettingsDep,
    get_document_service,
    get_job_runner,
    owner_scope,
)
from app.api.errors import PayloadTooLargeError
from app.core.exceptions import ValidationError
from app.schemas.document import (
    DocumentListResponse,
    DocumentMetadata,
    DocumentRead,
    DocumentUploadResponse,
    RetryResponse,
)
from app.services.document_service import DocumentService

__all__ = ["router"]

router = APIRouter(tags=["documents"])

#: The number of bytes that are read from the upload in one step.
UPLOAD_CHUNK_SIZE = 1024 * 1024

#: The maximum number of documents a single page may contain.
MAX_PAGE_SIZE = 100


async def _read_upload(file: UploadFile, max_bytes: int) -> bytes:
    """Return the content of *file*.

    The file is read in bounded chunks and the read is aborted as soon as
    the payload is larger than *max_bytes*, therefore a hostile upload can
    never exhaust the memory of the process.

    Raises
    ------
    app.api.errors.PayloadTooLargeError
        If the payload is larger than *max_bytes*.
    """
    buffer = bytearray()
    while True:
        chunk = await file.read(UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise PayloadTooLargeError(
                "the uploaded document exceeds the maximum allowed size",
                details={"max_upload_size_bytes": max_bytes},
            )
    return bytes(buffer)


def _metadata(
    company_name: str | None,
    document_title: str | None,
    document_type: str | None,
    fiscal_period: str | None,
    source_url: str | None,
) -> DocumentMetadata:
    """Return the metadata of the upload.

    Raises
    ------
    app.core.exceptions.ValidationError
        If a metadata value does not satisfy the schema.
    """
    try:
        return DocumentMetadata(
            company_name=company_name,
            document_title=document_title,
            document_type=document_type,
            fiscal_period=fiscal_period,
            source_url=source_url,
        )
    except PydanticValidationError as exc:
        raise ValidationError(
            "the metadata of the upload was rejected",
            code="invalid_document_metadata",
            details={"issues": [str(error) for error in exc.errors()]},
        ) from exc


@router.post(
    "/workspaces/{workspace_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document into a workspace",
)
async def upload_document(
    workspace_id: UUID,
    file: Annotated[UploadFile, File(description="The PDF document to upload")],
    settings: SettingsDep,
    service: Annotated[DocumentService, Depends(get_document_service)],
    runner: Annotated[JobRunner, Depends(get_job_runner)],
    current_user: CurrentUserDep,
    company_name: Annotated[str | None, Form()] = None,
    document_title: Annotated[str | None, Form()] = None,
    document_type: Annotated[str | None, Form()] = None,
    fiscal_period: Annotated[str | None, Form()] = None,
    source_url: Annotated[str | None, Form()] = None,
) -> DocumentUploadResponse:
    """Upload a document, register it and hand it to the job runner.

    The status that is returned is the **real** status of the document at
    the moment the answer is written.  With the inline runner the document
    was processed completely, with the background runner it is still being
    processed - both are reported honestly.
    """
    payload = await _read_upload(file, settings.max_upload_size_bytes)
    metadata = _metadata(
        company_name,
        document_title,
        document_type,
        fiscal_period,
        source_url,
    )

    registration = service.register_upload(
        workspace_id=workspace_id,
        filename=file.filename or "document.pdf",
        data=payload,
        declared_mime_type=file.content_type,
        metadata=metadata,
        owner_id=owner_scope(current_user),
    )

    if registration.duplicate:
        # The document already exists: it is not processed a second time,
        # the existing document is reported instead.
        document = service.get_document(
            registration.document_id, owner_id=owner_scope(current_user)
        )
        return DocumentUploadResponse(
            document_id=document.id,
            processing_status=document.processing_status,
            processing_stage=document.processing_stage,
            content_hash=document.content_hash,
            duplicate=True,
        )

    runner.submit(registration.document_id)
    document = service.get_document(
        registration.document_id, owner_id=owner_scope(current_user)
    )
    return DocumentUploadResponse(
        document_id=document.id,
        processing_status=document.processing_status,
        processing_stage=document.processing_stage,
        content_hash=document.content_hash,
        duplicate=False,
    )


@router.get(
    "/workspaces/{workspace_id}/documents",
    response_model=DocumentListResponse,
    summary="List the documents of a workspace",
)
def list_documents(
    workspace_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: CurrentUserDep,
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    document_type: str | None = Query(default=None, max_length=64),
    company_name: str | None = Query(default=None, max_length=255),
) -> DocumentListResponse:
    """Return a page of the documents of the workspace *workspace_id*.

    A workspace the user may not reach is answered with ``404``.
    """
    summaries, total = service.list_documents(
        workspace_id,
        limit=limit,
        offset=offset,
        status=status_filter,
        document_type=document_type,
        company_name=company_name,
        owner_id=owner_scope(current_user),
    )
    return DocumentListResponse(
        items=[DocumentRead.model_validate(summary) for summary in summaries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentRead,
    summary="Return a single document",
)
def get_document(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: CurrentUserDep,
) -> DocumentRead:
    """Return the document *document_id*.

    A document of a workspace the user may not reach is answered with
    ``404``: the existence of a document of somebody else is never
    disclosed.
    """
    summary = service.get_document(document_id, owner_id=owner_scope(current_user))
    return DocumentRead.model_validate(summary)


@router.post(
    "/documents/{document_id}/retry",
    response_model=RetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry the processing of a failed document",
)
def retry_document(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    runner: Annotated[JobRunner, Depends(get_job_runner)],
    current_user: CurrentUserDep,
) -> RetryResponse:
    """Queue a new processing attempt for the document *document_id*.

    The document must be in the ``failed`` state, otherwise the request is
    rejected with ``409``.  A document the user may not reach is answered
    with ``404``.
    """
    job = service.retry_document(document_id, owner_id=owner_scope(current_user))
    runner.submit(document_id)
    return RetryResponse(
        document_id=job.document_id,
        job_id=job.job_id,
        attempt_count=job.attempt_count,
        processing_status=job.processing_status,
    )


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a document",
)
def delete_document(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: CurrentUserDep,
) -> Response:
    """Delete the document *document_id* and its chunks.

    A document the user may not reach is answered with ``404``.
    """
    service.delete_document(document_id, owner_id=owner_scope(current_user))
    return Response(status_code=status.HTTP_204_NO_CONTENT)