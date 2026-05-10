"""Strong validation for candidate dispatch plans."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.schemas.agent_outputs import ResourceAllocationOutput


class InventoryService(Protocol):
    async def get_resource(self, resource_id: str) -> dict[str, Any] | None: ...

    async def is_known_location(self, location: str) -> bool: ...


class ValidationFailure(BaseModel):
    resource_id: str
    rule: str
    message: str


class DispatchValidationResult(BaseModel):
    valid_allocations: list[ResourceAllocationOutput] = Field(default_factory=list)
    rejected_allocations: list[ValidationFailure] = Field(default_factory=list)


async def validate_dispatch_plan(
    allocations: list[dict],
    inventory_service: InventoryService,
) -> DispatchValidationResult:
    valid: list[ResourceAllocationOutput] = []
    rejected: list[ValidationFailure] = []

    for allocation in allocations:
        resource_id = str(allocation.get("resource_id") or "")
        try:
            quantity = int(allocation.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0
        target_location = str(allocation.get("target_location") or allocation.get("to_location") or "")

        resource = await inventory_service.get_resource(resource_id) if resource_id else None
        if resource is None:
            rejected.append(ValidationFailure(resource_id=resource_id, rule="existence", message="resource_id does not exist"))
            continue

        available_quantity = int(resource.get("quantity") or resource.get("available_quantity") or 0)
        if quantity <= 0 or quantity > available_quantity:
            rejected.append(ValidationFailure(resource_id=resource_id, rule="quantity", message="quantity exceeds available inventory"))
            continue

        if str(resource.get("status") or "").lower() != "available":
            rejected.append(ValidationFailure(resource_id=resource_id, rule="status", message="resource is not available"))
            continue

        if not await inventory_service.is_known_location(target_location):
            rejected.append(ValidationFailure(resource_id=resource_id, rule="location", message="target_location is not recognized"))
            continue

        valid.append(
            ResourceAllocationOutput(
                resource_id=resource_id,
                quantity=quantity,
                status=str(allocation.get("status") or "validated"),
                source_location=str(allocation.get("source_location") or allocation.get("from_location") or resource.get("location") or ""),
                target_location=target_location,
            )
        )

    return DispatchValidationResult(valid_allocations=valid, rejected_allocations=rejected)
