"""
Order payment processing step.

Example of using the OrderEvent contract: raw event is validated at input.
If the contract is not met, Pydantic raises ValidationError before processing
and the event may go to DLQ according to Motia configuration.
"""
from motia import FlowContext, queue

from contracts.v1.order import OrderEvent

config = {
    "name": "process_order_payment",
    "description": "Validates order event with OrderEvent and processes payment; fails if contract is not met.",
    "triggers": [queue("order_event")],
    "enqueues": ["order_payment_processed"],
    "flows": ["data-sentinel"],
}


async def handler(event_data: dict, ctx: FlowContext) -> None:
    """
    Receives raw event; validates with OrderEvent before any logic.
    Ensures invalid data is not processed: if contract fails, ValidationError
    is raised and the orchestrator may send to DLQ (UNPROCESSED_DLQ).
    """
    order = OrderEvent.model_validate(event_data)

    # Typed access and autocomplete
    ctx.logger.info(
        "Processing order",
        {
            "order_id": order.payload.order_id,
            "customer_email": str(order.payload.customer_email),
            "event_id": str(order.event_id),
            "version": order.version,
        },
    )
    # Real payment logic would go here (Stripe, etc.)
    await ctx.enqueue(
        {
            "topic": "order_payment_processed",
            "data": {
                "order_id": order.payload.order_id,
                "event_id": str(order.event_id),
                "total_amount": order.payload.total_amount,
                "currency": order.payload.currency,
            },
        }
    )
