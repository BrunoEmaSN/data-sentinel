"""
Step de procesamiento de pago de orden.

Ejemplo de uso del contrato OrderEvent: el evento crudo se valida en la entrada.
Si el contrato no se cumple, Pydantic lanza ValidationError antes de procesar
y el evento puede ir a DLQ según la configuración de Motia.
"""
from motia import FlowContext, queue

from contracts.v1.order import OrderEvent

config = {
    "name": "process_order_payment",
    "description": "Valida evento de orden con OrderEvent y procesa el pago; falla si el contrato no se cumple.",
    "triggers": [queue("order_event")],
    "enqueues": ["order_payment_processed"],
    "flows": ["data-sentinel"],
}


async def handler(event_data: dict, ctx: FlowContext) -> None:
    """
    Recibe el evento crudo; valida con OrderEvent antes de cualquier lógica.
    Garantiza que no se procesan datos inválidos: si el contrato falla, se lanza
    ValidationError y el orquestador puede enviar a DLQ (UNPROCESSED_DLQ).
    """
    order = OrderEvent.model_validate(event_data)

    # Acceso con tipado y autocompletado
    ctx.logger.info(
        "Procesando orden",
        {
            "order_id": order.payload.order_id,
            "customer_email": str(order.payload.customer_email),
            "event_id": str(order.event_id),
            "version": order.version,
        },
    )
    # Aquí iría la lógica real de pago (Stripe, etc.)
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
