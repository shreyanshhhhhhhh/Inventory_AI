from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_owner
from app.core.errors import AppError
from app.db import get_db
from app.models import User
from app.schemas.supplier_messages import (
    EmailSenderStatusResponse,
    SupplierMessageEditRequest,
    SupplierMessageRejectRequest,
    SupplierMessageResponse,
    SupplierMessageSendRequest,
)
from app.services.email_sender import sender_status
from app.services.supplier_messages import (
    SupplierMessageError,
    approve_and_send,
    edit_draft,
    reject_draft,
)

router = APIRouter(prefix="/supplier-messages", tags=["supplier-messages"])


def _business_id(user: User) -> str:
    if user.business_id is None or user.role is None:
        raise AppError("This account is not attached to a business.", code="forbidden", status_code=403)
    return user.business_id


def _raise(exc: SupplierMessageError) -> None:
    raise AppError(exc.message, code=exc.code, status_code=exc.status_code)


@router.get("/sender-status", response_model=EmailSenderStatusResponse)
def sender_status_route(
    user: User = Depends(get_current_user),
) -> EmailSenderStatusResponse:
    del user
    return EmailSenderStatusResponse.model_validate(sender_status())


@router.patch("/{message_id}", response_model=SupplierMessageResponse)
def edit_message_route(
    message_id: str,
    body: SupplierMessageEditRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
) -> SupplierMessageResponse:
    try:
        row = edit_draft(
            db,
            business_id=_business_id(user),
            actor_user_id=user.id,
            actor_role=user.role or "",
            message_id=message_id,
            subject=body.subject,
            body=body.body,
        )
    except SupplierMessageError as exc:
        _raise(exc)
    return SupplierMessageResponse.model_validate(row)


@router.post("/{message_id}/send", response_model=SupplierMessageResponse)
def send_message_route(
    message_id: str,
    body: SupplierMessageSendRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
) -> SupplierMessageResponse:
    payload = body or SupplierMessageSendRequest()
    try:
        row = approve_and_send(
            db,
            business_id=_business_id(user),
            actor_user_id=user.id,
            actor_role=user.role or "",
            message_id=message_id,
            subject=payload.subject,
            body=payload.body,
        )
    except SupplierMessageError as exc:
        _raise(exc)
    return SupplierMessageResponse.model_validate(row)


@router.post("/{message_id}/reject", response_model=SupplierMessageResponse)
def reject_message_route(
    message_id: str,
    body: SupplierMessageRejectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
) -> SupplierMessageResponse:
    try:
        row = reject_draft(
            db,
            business_id=_business_id(user),
            actor_user_id=user.id,
            actor_role=user.role or "",
            message_id=message_id,
            reason=body.reason,
        )
    except SupplierMessageError as exc:
        _raise(exc)
    return SupplierMessageResponse.model_validate(row)
