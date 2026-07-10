import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripePaymentService:
    @staticmethod
    def create_payment_sheet_params(amount_cents: int, user: object, reservation_id: str):
        """
        Gera os parâmetros necessários para o Stripe Payment Sheet (Capacitor/Nativo).
        """
        customers = stripe.Customer.list(email=user.email).data if hasattr(user, 'email') else []
        
        if customers:
            customer = customers[0]
        else:
            customer = stripe.Customer.create(
                name=user.name if hasattr(user, 'name') else str(user.id),
                email=user.email if hasattr(user, 'email') else None,
                metadata={'user_id': str(user.id)}
            )

        ephemeral_key = stripe.EphemeralKey.create(
            customer=customer.id,
            stripe_version='2023-10-16',
        )

        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='brl',
            customer=customer.id,
            automatic_payment_methods={'enabled': True}, 
            metadata={
                'user_id': str(user.id),
                'reservation_id': str(reservation_id)
            }
        )

        return {
            'paymentIntent': payment_intent.client_secret,
            'ephemeralKey': ephemeral_key.secret,
            'customer': customer.id,
            'publishableKey': settings.STRIPE_PUBLISHABLE_KEY
        }

    # 🌟 ATUALIZADO: Configurado estritamente para Cartão de Crédito na Web
    @staticmethod
    def create_checkout_session(amount_cents: int, ride: object, reservation_id: str):
        """
        Gera uma sessão de checkout hospedada no site do Stripe para navegadores.
        """
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'], # 🌟 Removido o 'pix' para testar direto no localhost sem erros!
            line_items=[{
                'price_data': {
                    'currency': 'brl',
                    'product_data': {
                        'name': f"Carona Solidária - Viagem #{str(ride.id)[:8]}",
                        'description': f"De {ride.origin} para {ride.destination}",
                    },
                    'unit_amount': amount_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"http://localhost:3000/runs?payment=success&res={reservation_id}",
            cancel_url=f"http://localhost:3000/runs?payment=cancel",
            metadata={'reservation_id': str(reservation_id)}
        )
        return checkout_session.url

    @staticmethod
    def refund_payment(payment_intent_id: str):
        try:
            return stripe.Refund.create(payment_intent=payment_intent_id)
        except stripe.error.StripeError as e:
            print(f"❌ Erro ao estornar no Stripe: {e}")
            return None