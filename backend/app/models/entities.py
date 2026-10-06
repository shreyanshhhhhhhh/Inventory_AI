from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import UtcDateTime, new_id, utcnow

MONEY = Numeric(18, 4)
QUANTITY = Numeric(14, 4)


class IdMixin:
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )


class Business(IdMixin, TimestampMixin, Base):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency_code: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IS NULL OR role IN ('owner', 'staff')",
            name="role_known",
        ),
    )

    business_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    invited_by_user_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )


class RefreshToken(IdMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)


class Location(IdMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_locations_business_id_name"),)

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class Category(IdMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_categories_business_id_name"),)

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("business_id", "sku", name="uq_products_business_id_sku"),)

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="each")
    cost: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    reorder_point: Mapped[Decimal | None] = mapped_column(QUANTITY, nullable=True)
    safety_stock: Mapped[Decimal | None] = mapped_column(QUANTITY, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class Supplier(IdMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint("lead_time_days >= 0", name="lead_time_nonnegative"),
    )

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class ProductSupplier(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_suppliers"
    __table_args__ = (
        UniqueConstraint("product_id", "supplier_id", name="uq_product_suppliers_product_id_supplier_id"),
        CheckConstraint("lead_time_days >= 0", name="lead_time_nonnegative"),
    )

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier_sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PurchaseOrder(IdMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("business_id", "po_number", name="uq_purchase_orders_business_id_po_number"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'sent', 'received', 'cancelled')",
            name="status_known",
        ),
    )

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    po_number: Mapped[str] = mapped_column(String(32), nullable=False)
    supplier_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    currency_code: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordered_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    expected_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )


class PurchaseOrderItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        CheckConstraint("quantity_ordered > 0", name="quantity_ordered_positive"),
    )

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    purchase_order_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity_ordered: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class StockMovement(IdMixin, Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('receipt', 'purchase_receipt', 'sale', 'adjustment', 'transfer')",
            name="movement_type_known",
        ),
        CheckConstraint(
            "movement_type != 'receipt' OR quantity > 0",
            name="manual_receipt_quantity_positive",
        ),
        CheckConstraint("quantity <> 0", name="quantity_nonzero"),
        CheckConstraint(
            "movement_type != 'purchase_receipt' OR quantity > 0",
            name="receipt_quantity_positive",
        ),
        CheckConstraint(
            "movement_type != 'sale' OR quantity < 0",
            name="sale_quantity_negative",
        ),
        CheckConstraint(
            "movement_type != 'adjustment' OR (reason IS NOT NULL AND length(trim(reason)) > 0)",
            name="adjustment_reason_nonblank",
        ),
        CheckConstraint(
            "(movement_type = 'transfer' AND transfer_group_id IS NOT NULL) "
            "OR (movement_type != 'transfer' AND transfer_group_id IS NULL)",
            name="transfer_group_iff_transfer",
        ),
        CheckConstraint(
            "(movement_type = 'sale' AND sale_group_id IS NOT NULL) "
            "OR (movement_type != 'sale' AND sale_group_id IS NULL)",
            name="sale_group_iff_sale",
        ),
        CheckConstraint(
            "(movement_type = 'purchase_receipt' AND purchase_order_item_id IS NOT NULL) "
            "OR (movement_type != 'purchase_receipt' AND purchase_order_item_id IS NULL)",
            name="receipt_links_po_item",
        ),
        Index("ix_stock_movements_on_hand", "business_id", "product_id", "location_id"),
        Index("ix_stock_movements_transfer_group_id", "transfer_group_id"),
        Index("ix_stock_movements_purchase_order_item_id", "purchase_order_item_id"),
    )

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    transfer_group_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    sale_group_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    purchase_order_item_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("purchase_order_items.id", ondelete="RESTRICT"),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)
    created_by_user_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )


class AutonomyRules(IdMixin, TimestampMixin, Base):
    __tablename__ = "autonomy_rules"
    __table_args__ = (UniqueConstraint("business_id", name="uq_autonomy_rules_business_id"),)

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    auto_approve_below_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint("actor_type IN ('user', 'agent')", name="actor_type_known"),
    )

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    before_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)


class AgentRun(IdMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'awaiting_approval', 'completed', 'failed', 'cancelled')",
            name="agent_run_status_known",
        ),
        Index("ix_agent_runs_business_id", "business_id"),
        Index("ix_agent_runs_actor_status", "actor_user_id", "status"),
    )

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    state_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    events_data: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AgentStep(IdMixin, Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        CheckConstraint("step_kind IN ('llm', 'tool')", name="agent_step_kind_known"),
        Index("ix_agent_steps_run_id", "run_id"),
        Index("ix_agent_steps_business_id", "business_id"),
    )

    run_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("agent_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    step_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)


class AgentSuggestion(IdMixin, Base):
    __tablename__ = "agent_suggestions"
    __table_args__ = (
        CheckConstraint(
            "suggestion_type IN ('generic', 'draft_po', 'draft_email')",
            name="agent_suggestion_type_known",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'dismissed')",
            name="agent_suggestion_status_known",
        ),
        Index("ix_agent_suggestions_business_id", "business_id"),
        Index("ix_agent_suggestions_run_id", "run_id"),
    )

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    run_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("agent_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    suggestion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)


class ConversationMessage(IdMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="chat_message_role_known"),
        Index("ix_chat_messages_user_created", "business_id", "user_id", "created_at"),
    )

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("agent_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)


class LlmUsageCounter(IdMixin, Base):
    __tablename__ = "llm_usage_counters"
    __table_args__ = (
        UniqueConstraint("business_id", "usage_date", name="uq_llm_usage_business_id_usage_date"),
    )

    business_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
